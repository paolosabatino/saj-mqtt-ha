DOMAIN = "saj_mqtt"

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
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
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
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
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
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging
import async_timeout
import asyncio
import time

_LOGGER = logging.getLogger("saj_mqtt")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

# realtime_data packet fields
MAP_SAJ_REALTIME_DATA = (
    # General info
    ("year", 0x0, ">H", None, None, None, None),
    ("month", 0x2, ">B", None, None, None, None),
    ("day", 0x3, ">B", None, None, None, None),
    ("hour", 0x4, ">B", None, None, None, None),
    ("minute", 0x5, ">B", None, None, None, None),
    ("second", 0x6, ">B", None, None, None, None),

    ("heatsink_temperature", 0x20, ">h", 0.1, TEMP_CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("earth_leakage_current_ma", 0x24, ">H", 1.0, ELECTRIC_CURRENT_MILLIAMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    # Power grid data
    ("grid_voltage", 0x62, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("grid_current", 0x64, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("grid_frequency", 0x66, ">H", 0.01, FREQUENCY_HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("grid_dc_component", 0x68, ">h", 0.001, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("grid_power_active", 0x6a, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("grid_power_apparent", 0x6c, ">H", 1.0, POWER_VOLT_AMPERE, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("grid_power_factor", 0x6e, ">h", 0.1, PERCENTAGE, SensorDeviceClass.POWER_FACTOR, SensorStateClass.MEASUREMENT),

    # Inverter power data
    ("inverter_voltage", 0x8c, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("inverter_current", 0x8e, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("inverter_frequency", 0x90, ">H", 0.01, FREQUENCY_HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("inverter_power_active", 0x92, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("inverter_power_apparent", 0x94, ">h", 1.0, POWER_VOLT_AMPERE, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("inverter_bus_master_voltage", 0xce, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("inverter_bus_slave_voltage", 0xd0, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),

    # Output power data
    ("output_voltage", 0xaa, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("output_current", 0xac, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("output_frequency", 0xae, ">H", 0.01, FREQUENCY_HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("output_dc_voltage", 0xb0, ">h", 0.001, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("output_power_active", 0xb2, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("output_power_apparent", 0xb4, ">h", 1.0, POWER_VOLT_AMPERE, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),

    # Battery data
    ("battery_voltage", 0xd2, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("battery_current", 0xd4, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_control_current1", 0xd6, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_control_current2", 0xd8, ">h", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_power", 0xda, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("battery_temperature", 0xdc, ">h", 0.1, TEMP_CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("battery_charge", 0xde, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),

    # Photovoltaic data
    ("panel_array1_voltage", 0xe2, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("panel_array1_current", 0xe4, ">H", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("panel_array1_power", 0xe6, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("panel_array2_voltage", 0xe8, ">H", 0.1, ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("panel_array2_current", 0xea, ">H", 0.01, ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("panel_array2_power", 0xec, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),

    # Power summaries
    ("summary_system_load", 0x140, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("smart_meter_load", 0x142, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_photovoltaic_power", 0x14a, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_battery_power", 0x14c, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_grid_power", 0x14e, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_inverter_power", 0x152, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_backup_load", 0x156, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT)

)

MAP_SAJ_ENERGY_STATS = (
    ('energy_photovoltaic', 0x17e),
    ('energy_battery_charging', 0x18e),
    ('energy_battery_used', 0x19e),
    ('energey_load_power', 0x1be),
    ('energy_backup_load', 0x1ce),
    ('energy_exported', 0x1de),
    ('energy_imported', 0x1ee)
)

# This list of sensors will be populated during setup phase with Sensor class instances
sensors = []

# Responses to MQTT data_transmission requests
responses = OrderedDict()

@attr.s(slots=True, frozen=True)
class ReceiveMessage:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: bytes = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()

def _handle_realtime_data(msg: ReceiveMessage) -> None:

    topic = msg.topic
    payload = msg.payload[0x24:0x224]

    _LOGGER.debug("Received message, topic: %s, length: %d" % (topic, len(payload)))

    for sensor in sensors:
        sensor.update(payload)

    _LOGGER.debug("Updated %d sensors" % (len(sensors),))

def _handle_data_transmission_rsp(msg: ReceiveMessage) -> None:

    topic = msg.topic
    payload = msg.payload

    try:
        req_id, size, content = parse_packet(payload)
        _LOGGER.debug("%s: req_id: 0x%x, content length: %d" % (topic, req_id, len(content)))

        if req_id in responses:
            responses[req_id] = content

    except Exception as err:
        _LOGGER.error("an error occurred while collecting data_transmission_rsp: %s" % (err,))

def forge_packet(start: int, count: int) -> bytes:
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

def parse_packet(packet):
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

async def _subscribe_topics(hass: HomeAssistant, sub_state: dict | None, serial_number: str) -> dict:
    # Optionally mark message handlers as callback

    topics = {
        "realtime_data": {
            "topic": f"saj/{serial_number}/realtime_data",
            "msg_callback": _handle_realtime_data,
            "encoding": None
        },
        "data_transmission_rsp": {
            "topic": f"saj/{serial_number}/data_transmission_rsp",
            "msg_callback": _handle_data_transmission_rsp,
            "encoding": None
        }
    }

    _LOGGER.debug("subscribing to topics %s" % (topics.keys(),))

    mqtt = hass.components.mqtt
    unsubscribe_callbacks = dict()

    for item, topic_data in topics.items():
        unsubscribe = await mqtt.async_subscribe(topic_data['topic'], topic_data['msg_callback'], 0x2, topic_data['encoding'])

    return unsubscribe_callbacks

async def _unsubscribe_topics(sub_state: dict | None) -> None:
    for item, callback in sub_state.items():
        await callback()

    return
    # return async_unsubscribe_topics(hass, sub_state)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:

    broker_host = config[CONF_HOST]
    serial_number = config[CONF_NAME]

    _LOGGER.info("setup_platform, broker host: %s - inverter serial: %s" % (broker_host, serial_number))

    try:
        sub_state = await _subscribe_topics(hass, None, serial_number)
    except HomeAssistantError as ex:
        raise PlatformNotReady(f"could not subscribe topics, reason: {ex}")

    _LOGGER.debug("subscription done")

    """Set up the sensor platform."""
    """
    for config_tuple in MAP_SAJ_REALTIME_DATA:

        # If a field has no SensorDeviceClass, skip the creation of the sensor
        if config_tuple[5] is None:
            continue

        sensor = Sensor(serial_number, config_tuple)
        sensors.append(sensor)

        _LOGGER.debug("created sensor %s" % (config_tuple[0],))
    """

    """
        Set up the energy data statistics sensors. For each "category" there are four spannig periods,
        so each category creates four sensors
    """
    for config_tuple in MAP_SAJ_ENERGY_STATS:

        name, offset = config_tuple

        for period in 'daily', 'monthly', 'yearly', 'total':
            sensor_name = f"{name}_{period}"
            sensor = EnergyStatSensor(serial_number, sensor_name, offset)
            sensors.append(sensor)

            _LOGGER.debug("created sensor %s" % (sensor_name,))

            offset += 4

    _LOGGER.info("populated %d sensors" % (len(sensors),))

    coordinator = SajMqttCoordinator(hass, serial_number)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.debug("coordinator initialized")

    polled_sensors = []
    for config_tuple in MAP_SAJ_REALTIME_DATA:

        # If a field has no SensorDeviceClass, skip the creation of the sensor
        if config_tuple[5] is None:
            continue

        sensor = PolledSensor(coordinator, serial_number, config_tuple)
        polled_sensors.append(sensor)

        _LOGGER.debug("created polled sensor %s" % (config_tuple[0],))

    add_entities(sensors)
    add_entities(polled_sensors)

class SajMqttCoordinator(DataUpdateCoordinator):
    """SAJ MQTT data update coordinator"""

    def __init__(self, hass: HomeAssistant, serial_number: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="saj_mqtt",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
        )

        self.hass = hass
        self.mqtt = hass.components.mqtt
        self.topic = f"saj/{serial_number}/data_transmission"

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        _LOGGER.info("SajMqttCoordinator async update")

        async with async_timeout.timeout(10):
            # Forge the MQTT data_transmission packets to send to the inverter
            packets = [
                forge_packet(0x4000, 0x64),
                forge_packet(0x4064, 0x64),
                forge_packet(0x40c8, 0x37)
            ]

            # Cleanup the previous responses, we don't need them anymore
            responses.clear()

            # Publish the request MQTT packets
            for packet, req_id in packets:
                responses[req_id] = None
                await self.mqtt.async_publish(self.hass, self.topic, packet, 2, False, None)
                _LOGGER.info("sent data_transmission MQTT packet with req_id: 0x%x" % (req_id, ))

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

            return data

class PolledSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, serial_number, config_tuple):
        super().__init__(coordinator)

        sensor_name, offset, data_type, scale, unit, device_class, state_class = config_tuple

        self.sensor_name = sensor_name
        self.data_type = data_type
        self.offset = offset
        self.scale = scale

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        self._attr_name = sensor_name
        self.serial_number = serial_number

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        payload = self.coordinator.data

        value, = unpack_from(self.data_type, payload, self.offset)

        _LOGGER.debug("sensor: %s, raw value: %s, scale: %s" % (self.sensor_name, value, self.scale))

        if self.scale is not None:
            value *= self.scale

        self._attr_native_value = value

        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"saj_mqtt_{self.serial_number}_{self._attr_name}"

class Sensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_should_poll = False

    def __init__(self, serial_number: str, config_tuple: tuple) -> None:
        self.serial_number = serial_number

        sensor_name, offset, data_type, scale, unit, device_class, state_class = config_tuple

        self.sensor_name = sensor_name
        self.data_type = data_type
        self.offset = offset
        self.scale = scale

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        self._attr_name = sensor_name

    def update(self, payload: bytes) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        value, = unpack_from(self.data_type, payload, self.offset)

        _LOGGER.debug("sensor: %s, raw value: %s, scale: %s" % (self.sensor_name, value, self.scale))

        if self.scale is not None:
            value *= self.scale

        self._attr_native_value = value

        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"saj_mqtt_{self.serial_number}_{self._attr_name}"

class EnergyStatSensor(SensorEntity):
    """
        Sensor specific for energy statistics.
        All the sensors of this kind use KWh as data type, scale is x0.01 and sensors are dword unsigned integers
    """

    _attr_should_poll = False

    def __init__(self, serial_number: str, sensor_name: str, offset: int) -> None:
        self.serial_number = serial_number

        self.sensor_name = sensor_name
        self.offset = offset

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._attr_name = sensor_name

    def update(self, payload: bytes) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        value, = unpack_from(">I", payload, self.offset)

        _LOGGER.debug("sensor: %s, raw value: %s" % (self.sensor_name, value))

        self._attr_native_value = value * 0.01

        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"saj_mqtt_{self.serial_number}_{self._attr_name}"
