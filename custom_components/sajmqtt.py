"""SAJ MQTT inverter client."""
import asyncio
from collections import OrderedDict
import contextlib
from datetime import datetime
from random import random
from struct import pack, unpack_from

from pymodbus.utilities import computeCRC

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    LOGGER,
    SAJ_MQTT_DATA_TRANSMISSION,
    SAJ_MQTT_DATA_TRANSMISSION_RESP,
    SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT,
    SAJ_MQTT_MAX_REGISTERS_PER_QUERY,
    SAJ_MQTT_QOS,
)


class SajMqtt:
    """SAJ MQTT inverter client instance."""

    def __init__(self, hass: HomeAssistant, serial_number: str) -> None:
        """Set up the SajMqtt class."""
        super().__init__()

        self.hass = hass
        self.mqtt = hass.components.mqtt
        self.serial_number = serial_number

        self.responses = OrderedDict()

        self.unsubscribe_callbacks = {}

    async def initialize(self) -> None:
        """Initialize."""
        self.unsubscribe_callbacks = await self._subscribe_topics()

    async def deinitialize(self) -> None:
        """Deinitialize."""
        for item, callback in self.unsubscribe_callbacks.items():
            await callback()

    def _parse_packet(self, packet):
        """Parse a mqtt response data_transmission_rsp payload packet."""
        length, req_id, timestamp, request = unpack_from(">HHIH", packet, 0x00)

        date = datetime.fromtimestamp(timestamp)
        (size,) = unpack_from(">B", packet, 0xA)
        content = packet[0xB : 0xB + size]
        (crc16,) = unpack_from(">H", packet, 0xB + size)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8 : 0xB + size])

        LOGGER.debug(f"Request id: {req_id:04x}")
        LOGGER.debug(f"Request type: {request:04x}")
        LOGGER.debug(f"Length: {length} bytes")
        LOGGER.debug(f"Timestamp: {date}")
        LOGGER.debug(f"Register size: {size}")
        LOGGER.debug(f"Register content: {':'.join(f'{byte:02x}' for byte in content)}")
        LOGGER.debug(f"CRC16: {crc16}: {'ok' if crc16 == calc_crc else 'bad'}")

        return req_id, size, content

    @callback
    def _handle_data_transmission_rsp(self, msg: ReceiveMessage) -> None:
        """Handle a single packet received from MQTT."""
        topic = msg.topic
        payload = msg.payload

        try:
            LOGGER.debug(f"Received {SAJ_MQTT_DATA_TRANSMISSION_RESP} packet")
            req_id, size, content = self._parse_packet(payload)
            if req_id in self.responses:
                LOGGER.debug("Required packet for request")
                self.responses[req_id] = content
        except Exception as ex:
            LOGGER.error(
                f"Error while handling {SAJ_MQTT_DATA_TRANSMISSION_RESP} packet: {ex}"
            )

    async def _subscribe_topics(self) -> dict:
        """Subscribe to MQTT topics."""
        topics = {
            SAJ_MQTT_DATA_TRANSMISSION_RESP: {
                "topic": f"saj/{self.serial_number}/{SAJ_MQTT_DATA_TRANSMISSION_RESP}",
                "msg_callback": self._handle_data_transmission_rsp,
                "qos": SAJ_MQTT_QOS,
                "encoding": None,
            }
        }
        LOGGER.debug(f"Subscribing to topics: {list(topics.keys())}")
        unsubscribe_callbacks = {}
        for item, topic_data in topics.items():
            unsubscribe_callbacks[item] = await self.mqtt.async_subscribe(
                topic_data["topic"],
                topic_data["msg_callback"],
                topic_data["qos"],
                topic_data["encoding"],
            )
        return unsubscribe_callbacks

    def forge_packet(self, start: int, count: int) -> tuple[bytes, int]:
        """Forge a data_transmission packet.

        Make a data_transmission mqtt body content to request registers from start for the given amount of registers.
        We can query up to 123 registers with a single request.
        """

        LOGGER.debug("Creating MQTT packet")
        content = pack(">BBHH", 0x01, 0x03, start, count)
        crc16 = computeCRC(content)

        req_id = int(random() * 65536)
        rand = int(random() * 65536)
        packet = pack(">HBBH", req_id, 0x58, 0xC9, rand) + content + pack(">H", crc16)
        LOGGER.debug(
            f"Packet request id: {req_id:04x} - CRC16: {crc16:04x} - random: {rand:04x}"
        )
        LOGGER.debug(f"Packet length: {len(packet)} bytes")
        packet = pack(">H", len(packet)) + packet

        return packet, req_id

    async def query(
        self,
        start_register: int,
        count: int,
        timeout: int = SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT,
    ) -> bytearray | None:
        """Query the inverter for a number of registers.

        This method hides all the package splitting and
        returns the raw bytes if successful, or raises a timeout exception in
        case the results do not arrive or None in case data could not be sent
        """
        LOGGER.debug("Querying inverter")
        self.responses.clear()  # clear previous responses
        topic = f"saj/{self.serial_number}/{SAJ_MQTT_DATA_TRANSMISSION}"

        # Create the MQTT data_transmission packets to send to the inverter
        packets: list[tuple[bytes, int]] = []
        while count > 0:
            regs_count = min(count, SAJ_MQTT_MAX_REGISTERS_PER_QUERY)
            packet = self.forge_packet(start_register, regs_count)
            packets.append(packet)
            start_register += regs_count
            count -= regs_count
        try:
            async with asyncio.timeout(timeout):
                # Publish the packets
                for packet, req_id in packets:
                    self.responses[req_id] = None
                    LOGGER.debug(
                        f"Publishing packet with request id: {f'{req_id:04x}'}"
                    )
                    await self.mqtt.async_publish(
                        self.hass, topic, packet, 2, False, None
                    )
                LOGGER.debug("All packets published")

                # Wait for the answer packets
                while True:
                    LOGGER.debug(
                        f"Waiting for responses with request id: {[f'{k:04x}' for k in self.responses]}"
                    )
                    if all(self.responses.values()) is True:
                        break
                    await asyncio.sleep(1)
                LOGGER.debug("All responses received")

                # Concatenate the payloads, so we get the full answer
                data = bytearray()
                for req_id, response in self.responses.items():
                    data += response

        except asyncio.TimeoutError:
            LOGGER.warning(
                "Timeout error: the inverter did not answer in expected timeout"
            )
            data = None
        except HomeAssistantError as ex:
            LOGGER.warning(
                f"Could not publish {SAJ_MQTT_DATA_TRANSMISSION} packets, reason: {ex}"
            )
            data = None

        # Cleanup self.responses from request ids generated in this method
        for packet, req_id in packets:
            with contextlib.suppress(KeyError):
                del self.responses[req_id]

        return data
