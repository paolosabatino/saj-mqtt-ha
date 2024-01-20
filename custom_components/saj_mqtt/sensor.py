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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SERIAL_NUMBER,
    DATA_CONFIG,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    WorkingMode,
)
from .coordinator import SajMqttCoordinator

# fmt: off

# Sensor description format:
# (name, offset, data_type, scale, unit, device_class, state_class, enabled_default)

# inverter info packet fields
MAP_SAJ_INVERTER_INFO = (
    ("inverter_type", 0, ">H", None, None, None, None, False),
    ("inverter_sub_type", 2, ">H", None, None, None, None, False),
    ("inverter_comm_pro_version", 4, ">H", 0.001, None, None, None, False),
    ("inverter_serial_number", 6, ">S20", None, None, None, None, False),
    ("inverter_product_code", 26, ">S20", None, None, None, None, False),
    ("inverter_display_sw_version", 46, ">H", 0.001, None, None, None, False),
    ("inverter_master_control_sw_version", 48, ">H", 0.001, None, None, None, False),
    ("inverter_slave_control_sw_version", 50, ">H", 0.001, None, None, None, False),
    ("inverter_display_board_hw_version", 52, ">H", 0.001, None, None, None, False),
    ("inverter_control_board_hw_version", 54, ">H", 0.001, None, None, None, False),
    ("inverter_power_board_hw_version", 56, ">H", 0.001, None, None, None, False),
    ("inverter_battery_numbers", 58, ">H", None, None, None, None, False),
)

# battery info packet fields
MAP_SAJ_BATTERY_INFO = (
    ("battery_1_bms_type", 0, ">H", None, None, None, None, False),
    ("battery_1_bms_serial_number", 2, ">S16", None, None, None, None, False),
    ("battery_1_bms_sf_version", 18, ">H", 0.001, None, None, None, False),
    ("battery_1_bms_hw_version", 20, ">H", 0.001, None, None, None, False),
    ("battery_1_type", 22, ">H", None, None, None, None, False),
    ("battery_1_serial_number", 24, ">S16", None, None, None, None, False),
    ("battery_2_bms_type", 40, ">H", None, None, None, None, False),
    ("battery_2_bms_serial_number", 42, ">S16", None, None, None, None, False),
    ("battery_2_bms_sf_version", 58, ">H", 0.001, None, None, None, False),
    ("battery_2_bms_hw_version", 60, ">H", 0.001, None, None, None, False),
    ("battery_2_type", 62, ">H", None, None, None, None, False),
    ("battery_2_serial_number", 64, ">S16", None, None, None, None, False),
    ("battery_3_bms_type", 80, ">H", None, None, None, None, False),
    ("battery_3_bms_serial_number", 82, ">S16", None, None, None, None, False),
    ("battery_3_bms_sf_version", 98, ">H", 0.001, None, None, None, False),
    ("battery_3_bms_hw_version", 100, ">H", 0.001, None, None, None, False),
    ("battery_3_type", 102, ">H", None, None, None, None, False),
    ("battery_3_serial_number", 104, ">S16", None, None, None, None, False),
    ("battery_4_bms_type", 120, ">H", None, None, None, None, False),
    ("battery_4_bms_serial_number", 122, ">S16", None, None, None, None, False),
    ("battery_4_bms_sf_version", 138, ">H", 0.001, None, None, None, False),
    ("battery_4_bms_hw_version", 140, ">H", 0.001, None, None, None, False),
    ("battery_4_type", 142, ">H", None, None, None, None, False),
    ("battery_4_serial_number", 144, ">S16", None, None, None, None, False),
)

# battery controller data packet fields
MAP_SAJ_BATTERY_CONTROLLER_DATA = (
    ("battery_numbers", 0, ">H", None, None, None, None, False),
    ("battery_capacity", 2, ">H", None, "AH", None, None, False),
    ("battery_1_fault", 4, ">H", None, None, None, None, False),
    ("battery_1_warning", 6, ">H", None, None, None, None, False),
    ("battery_2_fault", 8, ">H", None, None, None, None, False),
    ("battery_2_warning", 10, ">H", None, None, None, None, False),
    ("battery_3_fault", 12, ">H", None, None, None, None, False),
    ("battery_3_warning", 14, ">H", None, None, None, None, False),
    ("battery_4_fault", 16, ">H", None, None, None, None, False),
    ("battery_4_warning", 18, ">H", None, None, None, None, False),
    #("controller_reserve", 20, ">HH", None, None, None, None, False),
    ("battery_1_soc", 24, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_1_soh", 26, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_1_voltage", 28, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, False),
    ("battery_1_current", 30, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, False),
    ("battery_1_temperature", 32, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, False),
    ("battery_1_cycle_num", 34, ">H", None, None, None, None, False),
    ("battery_2_soc", 36, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_2_soh", 38, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_2_voltage", 40, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, False),
    ("battery_2_current", 42, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, False),
    ("battery_2_temperature", 44, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, False),
    ("battery_2_cycle_num", 46, ">H", None, None, None, None, False),
    ("battery_3_soc", 48, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_3_soh", 50, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_3_voltage", 52, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, False),
    ("battery_3_current", 54, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, False),
    ("battery_3_temperature", 56, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, False),
    ("battery_3_cycle_num", 58, ">H", None, None, None, None, False),
    ("battery_4_soc", 60, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_4_soh", 62, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, False),
    ("battery_4_voltage", 64, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, False),
    ("battery_4_current", 66, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, False),
    ("battery_4_temperature", 68, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, False),
    ("battery_4_cycle_num", 70, ">H", None, None, None, None, False),
)

# realtime data packet fields
MAP_SAJ_REALTIME_DATA = (
    # General info
    # ("year", 0x0, ">H", None, None, None, None, False),
    # ("month", 0x2, ">B", None, None, None, None, False),
    # ("day", 0x3, ">B", None, None, None, None, False),
    # ("hour", 0x4, ">B", None, None, None, None, False),
    # ("minute", 0x5, ">B", None, None, None, None, False),
    # ("second", 0x6, ">B", None, None, None, None, False),

    ("inverter_working_mode", 0x8, ">H", None, None, SensorDeviceClass.ENUM, WorkingMode, True),
    ("heatsink_temperature", 0x20, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, True),
    ("earth_leakage_current", 0x24, ">H", 1.0, UnitOfElectricCurrent.MILLIAMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),

    # Grid data
    ("grid_voltage", 0x62, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("grid_current", 0x64, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("grid_frequency", 0x66, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, True),
    ("grid_dc_component", 0x68, ">h", 0.001, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("grid_power_active", 0x6a, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("grid_power_apparent", 0x6c, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT, True),
    ("grid_power_factor", 0x6e, ">h", 0.1, PERCENTAGE, SensorDeviceClass.POWER_FACTOR, SensorStateClass.MEASUREMENT, True),

    # Inverter data
    ("inverter_voltage", 0x8c, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("inverter_current", 0x8e, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("inverter_frequency", 0x90, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, True),
    ("inverter_power_active", 0x92, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("inverter_power_apparent", 0x94, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT, True),
    ("inverter_bus_master_voltage", 0xce, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("inverter_bus_slave_voltage", 0xd0, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),

    # Output data
    ("output_voltage", 0xaa, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("output_current", 0xac, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("output_frequency", 0xae, ">H", 0.01, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, True),
    ("output_dc_voltage", 0xb0, ">h", 0.001, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("output_power_active", 0xb2, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("output_power_apparent", 0xb4, ">h", 1.0, UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, SensorStateClass.MEASUREMENT, True),

    # Battery data
    ("battery_voltage", 0xd2, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("battery_current", 0xd4, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("battery_control_current_1", 0xd6, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("battery_control_current_2", 0xd8, ">h", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("battery_power", 0xda, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("battery_temperature", 0xdc, ">h", 0.1, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, True),
    ("battery_soc", 0xde, ">H", 0.01, PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, True),

    # Photovoltaic data
    ("panel_array_1_voltage", 0xe2, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("panel_array_1_current", 0xe4, ">H", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("panel_array_1_power", 0xe6, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("panel_array_2_voltage", 0xe8, ">H", 0.1, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, True),
    ("panel_array_2_current", 0xea, ">H", 0.01, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, True),
    ("panel_array_2_power", 0xec, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),

    # Power summaries
    ("summary_system_load_power", 0x140, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_smart_meter_load_power_1", 0x142, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_photovoltaic_power", 0x14a, ">H", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_battery_power", 0x14c, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_grid_power", 0x14e, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_inverter_power", 0x152, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_backup_load_power", 0x156, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True),
    ("summary_smart_meter_load_power_2", 0x15a, ">h", 1.0, UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, True)
)

# realtime energy statistics packet fields
MAP_SAJ_REALTIME_ENERGY_STATS = (
    ('energy_photovoltaic', 0x17e, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_battery_charged', 0x18e, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_battery_discharged', 0x19e, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_system_load', 0x1be, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_backup_load', 0x1ce, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_grid_exported', 0x1de, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True),
    ('energy_grid_imported', 0x1ee, ">I", 0.01, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, True)
)

# fmt: on


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    coordinator: SajMqttCoordinator = hass.data[DOMAIN][DATA_COORDINATOR]
    serial_number: str = hass.data[DOMAIN][DATA_CONFIG][CONF_SERIAL_NUMBER]

    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, serial_number)},
        "name": f"SAJ {serial_number}",
        "manufacturer": MANUFACTURER,
        "model": "H1 series",
        "serial_number": serial_number,
    }

    LOGGER.info("Setting up sensors")
    sensors: list[SajMqttSensor] = []

    # Inverter info sensors
    for config_tuple in MAP_SAJ_INVERTER_INFO:
        sensor = SajMqttSensor(coordinator, "inverter_info", device_info, config_tuple)
        LOGGER.debug(f"Setting up inverter info sensor: {sensor.name}")
        sensors.append(sensor)

    # Battery info sensors
    for config_tuple in MAP_SAJ_BATTERY_INFO:
        sensor = SajMqttSensor(coordinator, "battery_info", device_info, config_tuple)
        LOGGER.debug(f"Setting up battery info sensor: {sensor.name}")
        sensors.append(sensor)

    # Battery controller data sensors
    for config_tuple in MAP_SAJ_BATTERY_CONTROLLER_DATA:
        sensor = SajMqttSensor(
            coordinator, "battery_controller_data", device_info, config_tuple
        )
        LOGGER.debug(f"Setting up battery controller data sensor: {sensor.name}")
        sensors.append(sensor)

    # Realtime data sensors
    for config_tuple in MAP_SAJ_REALTIME_DATA:
        sensor = SajMqttSensor(coordinator, "realtime_data", device_info, config_tuple)
        LOGGER.debug(f"Setting up realtime data sensor: {sensor.name}")
        sensors.append(sensor)

    # Energy statistics sensors
    for config_tuple in MAP_SAJ_REALTIME_ENERGY_STATS:
        (
            name,
            offset,
            data_type,
            scale,
            unit,
            device_class,
            state_class,
            enabled_default,
        ) = config_tuple
        # 4 statistics for each type
        for period in "daily", "monthly", "yearly", "total":
            # Create new config tuple with new name
            sensor_name = f"{name}_{period}"
            tmp_tuple = (
                sensor_name,
                offset,
                data_type,
                scale,
                unit,
                device_class,
                state_class,
                enabled_default,
            )
            sensor = SajMqttSensor(coordinator, "realtime_data", device_info, tmp_tuple)
            LOGGER.debug(f"Setting up energy statistics sensor: {sensor.name}")
            sensors.append(sensor)
            # Update offset for next period
            offset += 4

    # Add the entities (use update_before_add=True to fetch initial data)
    LOGGER.info(f"Setting up {len(sensors)} sensors")
    async_add_entities(sensors, update_before_add=True)


class SajMqttSensor(CoordinatorEntity, SensorEntity):
    """Saj mqtt sensor."""

    def __init__(
        self,
        coordinator: SajMqttCoordinator,
        coordinator_data_key: str,
        device_info: DeviceInfo,
        config_tuple,
    ) -> None:
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
            enabled_default,
        ) = config_tuple

        self.coordinator = coordinator  # set coordinator again for typing support
        self.coordinator_data_key = coordinator_data_key  # data key in coordinator data
        self.data_type: str = data_type
        self.offset: int = offset
        self.scale: float | int | None = scale
        self.unit: str | None = unit
        # Use state class as enum class when device class is ENUM
        self.enum_class = (
            state_class if device_class is SensorDeviceClass.ENUM else None
        )

        # Set entity attributes
        self._attr_unique_id = f"{DOMAIN}_{device_info['serial_number']}_{sensor_name}"
        self._attr_name = f"{DOMAIN}_{sensor_name}"
        self._attr_device_class = device_class
        # Clear state class when device class is ENUM
        self._attr_state_class = (
            state_class if device_class is not SensorDeviceClass.ENUM else None
        )
        self._attr_native_unit_of_measurement = unit
        # Set options as enum names when device class is ENUM
        self._attr_options = (
            [e.name for e in self.enum_class] if self.enum_class else None
        )
        self._attr_entity_registry_enabled_default = enabled_default

        # Set device info
        self._attr_device_info = device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        payload = self.coordinator.data[self.coordinator_data_key]
        if payload is None:
            return None

        # Get raw sensor value (>Sxx is custom type to indicate a string of length xx)
        if self.data_type.startswith(">S"):
            reg_length = int(self.data_type.replace(">S", ""))
            value = bytearray.decode(payload[self.offset : self.offset + reg_length])
        else:
            (value,) = unpack_from(self.data_type, payload, self.offset)

        # Set sensor value (taking scale into account, scale should ALWAYS contain a .)
        if self.scale is not None:
            value = round(value * self.scale, str(self.scale)[::-1].find("."))
        self._attr_native_value = value

        # Convert enum sensor to the corresponding enum name
        if self.enum_class:
            self._attr_native_value = self.enum_class(self._attr_native_value).name

        LOGGER.debug(
            f"Sensor: {self.name}, value: {value}{' ' + self.unit if self.unit else ''}"
        )

        self.async_write_ha_state()
