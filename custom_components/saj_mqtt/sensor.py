"""Support for SAJ MQTT sensors."""
from __future__ import annotations

from struct import unpack_from

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_SAJMQTT, DOMAIN, LOGGER
from .coordinator import SajMqttCoordinator
from .sajmqtt import SajMqtt

# fmt: off

# realtime data packet fields
MAP_SAJ_REALTIME_DATA = (
    # General info
    ("year", 0x0, ">H", None, None, None, None),
    ("month", 0x2, ">B", None, None, None, None),
    ("day", 0x3, ">B", None, None, None, None),
    ("hour", 0x4, ">B", None, None, None, None),
    ("minute", 0x5, ">B", None, None, None, None),
    ("second", 0x6, ">B", None, None, None, None),

    ("heatsink_temperature", 0x20, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("earth_leakage_current", 0x24, ">H", 1.0, UnitOfElectricCurrent.MILLIAMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),

    # Grid data
    ("grid_voltage", 0x62, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("grid_current", 0x64, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("grid_frequency", 0x66, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("grid_dc_component", 0x68, ">h", 0.001, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("grid_power_active", 0x6a, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("grid_power_apparent", 0x6c, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT),
    ("grid_power_factor", 0x6e, ">h", 0.1, PERCENTAGE, SensorDeviceClass.POWER_FACTOR, SensorStateClass.MEASUREMENT),

    # Inverter data
    ("inverter_voltage", 0x8c, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("inverter_current", 0x8e, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("inverter_frequency", 0x90, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("inverter_power_active", 0x92, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("inverter_power_apparent", 0x94, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT),
    ("inverter_bus_master_voltage", 0xce, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("inverter_bus_slave_voltage", 0xd0, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),

    # Output data
    ("output_voltage", 0xaa, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("output_current", 0xac, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("output_frequency", 0xae, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
    ("output_dc_voltage", 0xb0, ">h", 0.001, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("output_power_active", 0xb2, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("output_power_apparent", 0xb4, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT),

    # Battery data
    ("battery_voltage", 0xd2, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("battery_current", 0xd4, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_control_current_1", 0xd6, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_control_current_2", 0xd8, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("battery_power", 0xda, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("battery_temperature", 0xdc, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("battery_soc", 0xde, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),

    # Photovoltaic data
    ("panel_array_1_voltage", 0xe2, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("panel_array_1_current", 0xe4, ">H", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("panel_array_1_power", 0xe6, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("panel_array_2_voltage", 0xe8, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("panel_array_2_current", 0xea, ">H", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("panel_array_2_power", 0xec, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),

    # Power summaries
    ("summary_system_load_power", 0x140, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_smart_meter_load_power_1", 0x142, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_photovoltaic_power", 0x14a, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_battery_power", 0x14c, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_grid_power", 0x14e, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_inverter_power", 0x152, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_backup_load_power", 0x156, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("summary_smart_meter_load_power_2", 0x15a, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT)
)

MAP_SAJ_ENERGY_STATS = (
    ('energy_photovoltaic', 0x17e),
    ('energy_battery_charged', 0x18e),
    ('energy_battery_discharged', 0x19e),
    ('energy_system_load', 0x1be),
    ('energy_backup_load', 0x1ce),
    ('energy_grid_exported', 0x1de),
    ('energy_grid_imported', 0x1ee)
)

# fmt: on


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    saj_mqtt: SajMqtt = hass.data[DOMAIN][DATA_SAJMQTT]
    coordinator: SajMqttCoordinator = hass.data[DOMAIN][DATA_COORDINATOR]

    LOGGER.info("Setting up sensors")
    sensors = []

    # Realtime data sensors
    for config_tuple in MAP_SAJ_REALTIME_DATA:
        # If a field has no SensorDeviceClass, skip the creation of the sensor
        if config_tuple[5] is None:
            continue

        sensor = RealtimeDataSensor(coordinator, saj_mqtt.serial_number, config_tuple)
        LOGGER.debug(f"Setting up realtime data sensor: {sensor.name}")
        sensors.append(sensor)

    # Energy statistics sensors
    for config_tuple in MAP_SAJ_ENERGY_STATS:
        name, offset = config_tuple

        # 4 statistics for each type
        for period in "daily", "monthly", "yearly", "total":
            sensor_name = f"{name}_{period}"
            sensor = EnergyStatisticsSensor(
                coordinator, saj_mqtt.serial_number, sensor_name, offset
            )
            LOGGER.debug(f"Setting up energy statistics sensor: {sensor.name}")
            sensors.append(sensor)
            offset += 4

    # Add the entities (use update_before_add=True to fetch initial data)
    LOGGER.info(f"Setting up {len(sensors)} sensors")
    async_add_entities(sensors, update_before_add=True)


class RealtimeDataSensor(CoordinatorEntity, SensorEntity):
    """Realtime data sensor."""

    def __init__(self, coordinator, serial_number, config_tuple) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        (
            sensor_name,
            offset,
            data_type,
            scale,
            unit,
            device_class,
            state_class,
        ) = config_tuple

        self.serial_number = serial_number

        self.sensor_name = sensor_name
        self.data_type = data_type
        self.offset = offset
        self.scale = scale

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_name = f"{DOMAIN}_{self.sensor_name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        payload = self.coordinator.data
        if payload is None:
            return

        # Get raw sensor value
        (value,) = unpack_from(self.data_type, payload, self.offset)
        LOGGER.debug(f"Sensor: {self.name}, raw value: {value}, scale: {self.scale}")

        # Set sensor value (taking scale into account)
        if self.scale is not None:
            value *= self.scale
        self._attr_native_value = value

        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for the sensor."""
        return f"{DOMAIN}_{self.serial_number}_{self.sensor_name}"


class EnergyStatisticsSensor(CoordinatorEntity, SensorEntity):
    """Energy statistics sensor."""

    def __init__(
        self, coordinator, serial_number: str, sensor_name: str, offset: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.serial_number = serial_number

        self.sensor_name = sensor_name
        self.offset = offset
        self.scale = 0.01  # fixed scale for all energy statistics sensors

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_name = f"{DOMAIN}_{self.sensor_name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        payload = self.coordinator.data
        if payload is None:
            return

        # Get raw sensor value
        (value,) = unpack_from(">I", payload, self.offset)
        LOGGER.debug(f"Sensor: {self.name}, raw value: {value}, scale: {self.scale}")

        # Set sensor value (taking fixed scale into account)
        self._attr_native_value = value * self.scale

        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for the sensor."""
        return f"{DOMAIN}_{self.serial_number}_{self.sensor_name}"
