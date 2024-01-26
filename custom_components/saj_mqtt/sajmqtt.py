"""SAJ MQTT inverter client."""
from __future__ import annotations

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
    MODBUS_DEVICE_ADDRESS,
    MODBUS_MAX_REGISTERS_PER_QUERY,
    MODBUS_READ_REQUEST,
    MODBUS_WRITE_REQUEST,
    SAJ_MQTT_DATA_TRANSMISSION,
    SAJ_MQTT_DATA_TRANSMISSION_RSP,
    SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT,
    SAJ_MQTT_ENCODING,
    SAJ_MQTT_QOS,
    SAJ_MQTT_RETAIN,
)
from .utils import debug, log_hex


class SajMqtt:
    """SAJ MQTT inverter client instance."""

    def __init__(
        self, hass: HomeAssistant, serial_number: str, debug_mqtt: bool
    ) -> None:
        """Set up the SajMqtt class."""
        super().__init__()

        self.hass = hass
        self.mqtt = hass.components.mqtt
        self.serial_number = serial_number
        self.debug_mqtt = debug_mqtt
        self.topic_data_transmission = (
            f"saj/{self.serial_number}/{SAJ_MQTT_DATA_TRANSMISSION}"
        )
        self.topic_data_transmission_rsp = (
            f"saj/{self.serial_number}/{SAJ_MQTT_DATA_TRANSMISSION_RSP}"
        )

        self.read_responses = OrderedDict()
        self.write_responses = OrderedDict()

        self.unsubscribe_callbacks = {}

    async def initialize(self) -> None:
        """Initialize."""
        self.unsubscribe_callbacks = await self._subscribe_topics()

    async def deinitialize(self) -> None:
        """Deinitialize.

        Currently not used, as we set up via async_setup_platform(), which doesn't support unloading
        """
        for unsubscribe_callback in self.unsubscribe_callbacks.values():
            await unsubscribe_callback()

    async def read_registers(
        self,
        register_start: int,
        register_count: int,
        timeout: int = SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT,
    ) -> bytearray | None:
        """Read 1 or more registers from the inverter.

        We can read up to 123 registers with a single request.
        Because a modbus response cannot exceed 256 bytes. (123 registers = 246 bytes, plus some overhead)
        This method hides all the package splitting and returns the raw bytes if successful.
        It returns None in case data could not be retrieved in time.
        """
        debug(
            f"Reading registers at {log_hex(register_start)}, length: {log_hex(register_count)}"
        )

        # Create the MQTT data_transmission packets to send to the inverter
        packets: list[tuple[bytes, int]] = []
        while register_count > 0:
            reg_count = min(register_count, MODBUS_MAX_REGISTERS_PER_QUERY)
            packet = self._create_mqtt_read_packet(register_start, reg_count)
            packets.append(packet)
            register_start += reg_count
            register_count -= reg_count
        try:
            async with asyncio.timeout(timeout):
                # Publish the packets
                req_ids = []
                for packet, req_id in packets:
                    req_ids.append(req_id)
                    self.read_responses[req_id] = None
                    debug(
                        f"Publishing packet with request id: {f'{log_hex(req_id)}'}",
                        self.debug_mqtt,
                    )
                    await self.mqtt.async_publish(
                        self.hass,
                        self.topic_data_transmission,
                        packet,
                        qos=SAJ_MQTT_QOS,
                        retain=SAJ_MQTT_RETAIN,
                        encoding=SAJ_MQTT_ENCODING,
                    )
                debug("All packets published", self.debug_mqtt)

                # Wait for the answer packets
                while True:
                    responses = OrderedDict(
                        (k, self.read_responses[k])
                        for k in req_ids
                        if k in self.read_responses
                    )
                    if all(responses.values()) is True:
                        break
                    debug(
                        f"Waiting for responses with request id: {[f'{log_hex(k)}' for k in req_ids if responses[k] is None]}",
                        self.debug_mqtt,
                    )
                    await asyncio.sleep(1)
                debug("All responses received", self.debug_mqtt)

                # Concatenate the payloads, so we get the full answer
                data = bytearray()
                for response in responses.values():
                    data += response

        except asyncio.TimeoutError:
            LOGGER.warning(
                "Timeout error: the inverter did not answer in the expected timeout"
            )
            data = None
        except HomeAssistantError as ex:
            LOGGER.warning(
                f"Could not publish {SAJ_MQTT_DATA_TRANSMISSION} packets, reason: {ex}"
            )
            data = None

        # Remove req_ids from self.read_responses
        for req_id in req_ids:
            with contextlib.suppress(KeyError):
                del self.read_responses[req_id]

        return data

    async def write_register(
        self,
        register: int,
        value: int,
        timeout: int = SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT,
    ) -> int | None:
        """Write a register value to the inverter."""
        debug(f"Writing register {log_hex(register)} with value {log_hex(value)}")

        # Create the MQTT data_transmission packet to send to the inverter
        packet, req_id = self._create_mqtt_write_packet(register, value)
        try:
            async with asyncio.timeout(timeout):
                # Publish packet
                self.write_responses[req_id] = None
                debug(
                    f"Publishing packet with request id: {f'{log_hex(req_id)}'}",
                    self.debug_mqtt,
                )
                await self.mqtt.async_publish(
                    self.hass,
                    self.topic_data_transmission,
                    packet,
                    qos=SAJ_MQTT_QOS,
                    retain=SAJ_MQTT_RETAIN,
                    encoding=SAJ_MQTT_ENCODING,
                )

                # Wait for the answer packet (check if not None, as we can also get 0 as response)
                while True:
                    if self.write_responses[req_id] is not None:
                        break
                    debug(
                        f"Waiting for response with request id: {f'{log_hex(req_id)}' if self.write_responses[req_id] is None else ''}",
                        self.debug_mqtt,
                    )
                    await asyncio.sleep(1)
                debug("Response received", self.debug_mqtt)

                # Get the answer
                data = self.write_responses[req_id]

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

        # Cleanup self.write_responses from request id generated in this method
        with contextlib.suppress(KeyError):
            del self.write_responses[req_id]

        return data

    async def _subscribe_topics(self) -> dict:
        """Subscribe to MQTT topics."""
        topics = {
            SAJ_MQTT_DATA_TRANSMISSION_RSP: {
                "topic": self.topic_data_transmission_rsp,
                "msg_callback": self._handle_data_transmission_rsp,
                "qos": SAJ_MQTT_QOS,
                "encoding": SAJ_MQTT_ENCODING,
            }
        }

        debug(f"Subscribing to topics: {list(topics.keys())}")
        unsubscribe_callbacks = {}
        for item, topic_data in topics.items():
            unsubscribe_callbacks[item] = await self.mqtt.async_subscribe(
                topic_data["topic"],
                topic_data["msg_callback"],
                qos=topic_data["qos"],
                encoding=topic_data["encoding"],
            )

        return unsubscribe_callbacks

    @callback
    def _handle_data_transmission_rsp(self, msg: ReceiveMessage) -> None:
        """Handle a single packet received from MQTT."""
        try:
            debug(f"Received {SAJ_MQTT_DATA_TRANSMISSION_RSP} packet", self.debug_mqtt)
            req_id, content = self._parse_packet(msg.payload)
            if req_id in self.read_responses:
                self.read_responses[req_id] = content
            if req_id in self.write_responses:
                self.write_responses[req_id] = content
        except Exception as ex:
            LOGGER.error(
                f"Error while handling {SAJ_MQTT_DATA_TRANSMISSION_RSP} packet: {ex}"
            )

    def _parse_packet(self, packet) -> tuple[int, bytearray | int]:
        """Parse a mqtt response data_transmission_rsp payload packet.

        Packet consists of [HEADER][PACKET_DATA]:
        - [HEADER] consists of [LENGTH][REQ_ID][TIMESTAMP][REQ_TYPE]
        - [PACKET_DATA] see specific packet parsing
        """
        # Parse the header
        length, req_id, timestamp, req_type = unpack_from(">HHIH", packet, 0x00)
        req_type -= (
            0x100  # substract 0x100 to match the request type (modbus read or write)
        )
        date = datetime.fromtimestamp(timestamp)

        debug(f"Request id: {log_hex(req_id)}", self.debug_mqtt)
        debug(f"Request type: {log_hex(req_type)}", self.debug_mqtt)
        debug(f"Length: {length} bytes", self.debug_mqtt)
        debug(f"Timestamp: {date}", self.debug_mqtt)

        if req_type == MODBUS_READ_REQUEST:
            content = self._parse_read_packet(packet)
        elif req_type == MODBUS_WRITE_REQUEST:
            content = self._parse_write_packet(packet)
        else:
            raise ValueError(f"Unsupported request type: {log_hex(req_type)}")

        return req_id, content

    def _parse_read_packet(self, packet) -> bytearray:
        """Parse a mqtt read packet.

        Packet consists of [SIZE][CONTENT][CRC]:
        - [SIZE] of the following content
        - [CONTENT] of the registers
        - [CRC] checksum
        """
        # Get the size of the content
        (size,) = unpack_from(">B", packet, 0xA)

        # Get the content
        content = packet[0xB : 0xB + size]

        # Get the CRC
        (crc16,) = unpack_from(">H", packet, 0xB + size)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8 : 0xB + size])

        debug(f"Response length: {size} bytes", self.debug_mqtt)
        debug(
            f"Response bytes: {':'.join(f'{b:02x}' for b in content)}", self.debug_mqtt
        )
        debug(
            f"CRC16: {log_hex(crc16)} -> {'ok' if crc16 == calc_crc else 'bad'}",
            self.debug_mqtt,
        )

        if crc16 != calc_crc:
            raise ValueError("Invalid CRC: expected {calc_crc}, received {crc16}")

        return content

    def _parse_write_packet(self, packet) -> int:
        """Parse a mqtt write packet.

        Packet consists of [REGISTER][VALUE][CRC]:
        - [REGISTER] to which the value was written
        - [VALUE] written to the register
        - [CRC] checksum
        """
        register, value, orig_crc16 = unpack_from(">HHH", packet, 0xA)

        # Get the CRC
        (crc16,) = unpack_from(">H", packet, 0xE)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8:0xE])

        debug(f"Written register: {log_hex(register)}", self.debug_mqtt)
        debug(f"Written value: {log_hex(value)}", self.debug_mqtt)
        debug(
            f"CRC16: {log_hex(crc16)} -> {'ok' if crc16 == calc_crc else 'bad'}",
            self.debug_mqtt,
        )

        if crc16 != calc_crc:
            raise ValueError("Invalid CRC: expected {calc_crc}, received {crc16}")

        return value

    def _create_mqtt_read_packet(self, start: int, count: int) -> tuple[bytes, int]:
        """Create a mqtt read packet.

        Create the data_transmission mqtt body content to read registers from start for the given amount of registers.

        Packet consists of [LENTH][HEADER][CONTENT][CRC]:
        - [LENGTH] of [HEADER][CONTENT][CRC]
        - [HEADER] consists of [REQ_ID][0x58][0xC9][RANDOM]
        - [CONTENT] consists of [DEVICE_ADDRESS][REQ_TYPE][REGISTER_START][REGISTER_COUNT]
        - [CRC] checksum
        """
        debug("Creating mqtt read packet", self.debug_mqtt)
        content = pack(
            ">BBHH", MODBUS_DEVICE_ADDRESS, MODBUS_READ_REQUEST, start, count
        )

        return self._create_modbus_mqtt_packet(MODBUS_READ_REQUEST, content)

    def _create_mqtt_write_packet(self, register: int, value: int) -> tuple[bytes, int]:
        """Create a mqtt write packet.

        Create the data_transmission mqtt body content to write a value to a register.

        Packet consists of [LENTH][HEADER][CONTENT][CRC]:
        - [LENGTH] of [HEADER][CONTENT][CRC]
        - [HEADER] consists of [REQ_ID][0x58][0xC9][RANDOM]
        - [CONTENT] consists of [DEVICE_ADDRESS][REQ_TYPE][REGISTER_START][REGISTER_COUNT]
        - [CRC] checksum
        """
        debug("Creating mqtt write packet", self.debug_mqtt)
        content = pack(
            ">BBHH", MODBUS_DEVICE_ADDRESS, MODBUS_WRITE_REQUEST, register, value
        )

        return self._create_modbus_mqtt_packet(MODBUS_WRITE_REQUEST, content)

    def _create_modbus_mqtt_packet(
        self, req_type: int, content: bytes
    ) -> tuple[bytes, int]:
        """Create a modbus mqtt packet.

        The mqtt packet encapsulates the modbus packet to interact with the interter.
        """
        # Compute CRC of modbus content
        crc16 = computeCRC(content)

        # Assemble the modbus content into the mqtt packet framework
        req_id = int(random() * 65536)
        rand = int(random() * 65536)
        packet = pack(">HBBH", req_id, 0x58, 0xC9, rand) + content + pack(">H", crc16)

        debug(f"Request id: {log_hex(req_id)}", self.debug_mqtt)
        debug(f"Request type: {log_hex(req_type)}", self.debug_mqtt)
        debug(f"CRC16: {log_hex(crc16)}", self.debug_mqtt)
        debug(f"Request length: {len(packet)} bytes", self.debug_mqtt)
        debug(f"Request bytes: {':'.join(f'{b:02x}' for b in packet)}", self.debug_mqtt)

        packet = pack(">H", len(packet)) + packet

        return packet, req_id
