import attr

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import UnitOfPower
from homeassistant.const import UnitOfEnergy

from homeassistant.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    POWER_VOLT_AMPERE,
    FREQUENCY_HERTZ,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    PERCENTAGE
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady, ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from typing import Awaitable, Callable, Union
from struct import unpack_from, pack
from pymodbus.utilities import computeCRC
from random import random
from collections import OrderedDict
from datetime import datetime, timedelta
from asyncio.exceptions import TimeoutError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging
import async_timeout
import asyncio
import time

_LOGGER = logging.getLogger("saj_mqtt")

@attr.s(slots=True, frozen=True)
class ReceiveMessage:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: bytes = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()

class SajMqtt(object):

    MQTT_DATA_TRANSMISSION = "data_transmission"
    MQTT_DATA_TRANSMISSION_RESP = "data_transmission_rsp"

    # We can query up to 123 registers per MQTT packet request, this
    # pseudo-constant controls the maximum number of registers to query
    # at once. The logic will split the request in multiple mqtt packets
    # automatically
    MAX_REGISTERS_PER_QUERY = 64

    def __init__(self, hass: HomeAssistant, serial_number: str):
        super().__init__()

        self.hass = hass
        self.mqtt = hass.components.mqtt
        self.serial_number = serial_number

        self.responses = OrderedDict()

        self.unsubscribe_callbacks = dict()

    async def initialize(self) -> None:
        """
            Do the subscription of the topics.
            If not possible, this call will raise a PlatformNotReady exception
            that must be caught by caller
        """
        self.unsubscribe_callbacks = await self._subscribe_topics()

    async def deinitialize(self) -> None:

        for item, callback in self.unsubscribe_callbacks.items():
            await callback()

        return

    def _parse_packet(self, packet):
        """
            Parses a mqtt response data_transmission_rsp payload packet
        """
        length, req_id, timestamp, request = unpack_from(">HHIH", packet, 0x00)

        date = datetime.fromtimestamp(timestamp)
        size, = unpack_from(">B", packet, 0xa)
        content = packet[0xb:0xb + size]
        crc16, = unpack_from(">H", packet, 0xb + size)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8:0xb + size])

        _LOGGER.debug("Packet length: %d bytes - Request ID: %4x - Request type: %4x" % (length, req_id, request))
        _LOGGER.debug("Timestamp: %s" % (date,))
        _LOGGER.debug("Register size: %d" % (size,))
        _LOGGER.debug("Register content: %s" % (":".join("%02x" % (byte,) for byte in content),))
        _LOGGER.debug("CRC16: %x: %s" % (crc16, "ok" if crc16 == calc_crc else "bad"))

        return req_id, size, content

    def _handle_data_transmission_rsp(self, msg: ReceiveMessage) -> None:
        """
            Handle the single packet arriving from MQTT
        """
        topic = msg.topic
        payload = msg.payload

        try:
            req_id, size, content = self._parse_packet(payload)
            _LOGGER.debug("%s: req_id: 0x%x, content length: %d" % (topic, req_id, len(content)))

            if req_id in self.responses:
                self.responses[req_id] = content

        except Exception as err:
            _LOGGER.error("an error occurred while collecting data_transmission_rsp: %s" % (err,))

    async def _subscribe_topics(self) -> dict:
        """
            Subscribe the topic to gather the answers from the inverter.
            In case MQTT is not ready yet, this will raise a PlatformNotReady exception
        """

        topics = {
            SajMqtt.MQTT_DATA_TRANSMISSION_RESP: {
                "topic": f"saj/{self.serial_number}/{SajMqtt.MQTT_DATA_TRANSMISSION_RESP}",
                "msg_callback": self._handle_data_transmission_rsp,
                "encoding": None
            }
        }

        _LOGGER.debug("subscribing to topics %s" % (topics.keys(),))

        mqtt = self.mqtt
        unsubscribe_callbacks = dict()

        for item, topic_data in topics.items():
            unsubscribe_callbacks[item] = await mqtt.async_subscribe(topic_data['topic'], topic_data['msg_callback'], 0x2, topic_data['encoding'])

        return unsubscribe_callbacks

    def forge_packet(self, start: int, count: int) -> bytes:
        """
            Make a data_transmission mqtt body content to request registers from start for the
            given amount of registers. We can query up to 123 registers with a single request
        """

        content = pack(">BBHH", 0x01, 0x03, start, count)
        crc16 = computeCRC(content)

        req_id = int(random() * 65536)
        rnd_value = int(random() * 65536)

        packet = pack(">HBBH", req_id, 0x58, 0xc9, rnd_value) + content + pack(">H", crc16)

        _LOGGER.debug("Request ID: %04x - CRC16: %04x - Random: %04x" % (req_id, crc16, rnd_value))
        _LOGGER.debug("Length: %d bytes" % (len(packet),))

        packet = pack(">H", len(packet)) + packet

        return packet, req_id

    async def query(self, start_register: int, count: int, timeout: int = 10) -> bytes | None:
        """
            Query a number of registers. This method hides all the package splitting and
            returns the raw bytes if successful, or raises a timeout exception in
            case the results do not arrive or None in case data could not be sent
        """

        _LOGGER.info("SajMqttCoordinator async update")

        mqtt = self.mqtt
        responses = self.responses
        topic = f"saj/{self.serial_number}/{SajMqtt.MQTT_DATA_TRANSMISSION}"

        responses.clear()

        # Forge the MQTT data_transmission packets to send to the inverter
        packets = []
        while count > 0:
            regs_count = min(count, SajMqtt.MAX_REGISTERS_PER_QUERY)
            packet = self.forge_packet(start_register, regs_count)
            packets.append(packet)
            start_register += regs_count
            count -= regs_count

        try:
            async with async_timeout.timeout(timeout):
                # Publish the request MQTT packets
                for packet, req_id in packets:
                    responses[req_id] = None
                    await mqtt.async_publish(self.hass, topic, packet, 2, False, None)
                    _LOGGER.debug("sent data_transmission MQTT packet with req_id: 0x%x" % (req_id, ))

                _LOGGER.info("sent done")

                # Wait for the answer packets
                while True:
                    if all(responses.values()) is True:
                        break
                    await asyncio.sleep(1)

                _LOGGER.info("answers received")

                # Concatenate the payloads, so we get the full answer
                data = bytearray()
                for req_id, response in responses.items():
                    data += response

        except TimeoutError as te:
            _LOGGER.warning("timeout error, inverter did not answer in expected timeout")
            data = None
        except HomeAssistantError as ex:
            _LOGGER.warning("could not send data_transmission MQTT packets, reason: %s" % (ex,))
            data = None

        # Cleanup self.responses from request ids generated in this method
        for packet, req_id in packets:
            try:
                del responses[req_id]
            except KeyError:
                pass

        return data
