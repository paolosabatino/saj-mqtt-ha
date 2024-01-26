"""The SAJ MQTT integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEBUG_MQTT,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_BATTERY_CONTROLLER,
    CONF_SCAN_INTERVAL_BATTERY_INFO,
    CONF_SCAN_INTERVAL_CONFIG,
    CONF_SCAN_INTERVAL_INVERTER_INFO,
    CONF_SERIAL_NUMBER,
    DATA_CONFIG,
    DATA_COORDINATOR,
    DATA_COORDINATOR_BATTERY_CONTROLLER,
    DATA_COORDINATOR_BATTERY_INFO,
    DATA_COORDINATOR_CONFIG,
    DATA_COORDINATOR_INVERTER_INFO,
    DATA_SAJMQTT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    SajMqttBatteryControllerDataCoordinator,
    SajMqttBatteryInfoDataCoordinator,
    SajMqttConfigDataCoordinator,
    SajMqttInverterInfoDataCoordinator,
    SajMqttRealtimeDataCoordinator,
)
from .sajmqtt import SajMqtt
from .services import async_register_services

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): cv.positive_time_period,
                vol.Optional(
                    CONF_SCAN_INTERVAL_INVERTER_INFO,
                    default=None,
                ): vol.Any(cv.positive_time_period, None),
                vol.Optional(
                    CONF_SCAN_INTERVAL_BATTERY_INFO,
                    default=None,
                ): vol.Any(cv.positive_time_period, None),
                vol.Optional(
                    CONF_SCAN_INTERVAL_BATTERY_CONTROLLER,
                    default=None,
                ): vol.Any(cv.positive_time_period, None),
                vol.Optional(
                    CONF_SCAN_INTERVAL_CONFIG,
                    default=None,
                ): vol.Any(cv.positive_time_period, None),
                vol.Optional(
                    CONF_DEBUG_MQTT,
                    default=False,
                ): vol.Any(cv.boolean),
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up using yaml config file."""
    # Set default hass data
    hass.data.setdefault(
        DOMAIN,
        {
            DATA_CONFIG: None,
            DATA_SAJMQTT: None,
            DATA_COORDINATOR: None,
            DATA_COORDINATOR_INVERTER_INFO: None,
            DATA_COORDINATOR_BATTERY_INFO: None,
            DATA_COORDINATOR_BATTERY_CONTROLLER: None,
            DATA_COORDINATOR_CONFIG: None,
        },
    )

    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        LOGGER.error("MQTT integration is not available")
        return False

    # Make sure SAJ MQTT integration is properly configured
    if DOMAIN not in config or CONF_SERIAL_NUMBER not in config[DOMAIN]:
        LOGGER.error("SAJ MQTT integration is not configured correctly")
        return False

    # Get config data
    conf = config[DOMAIN]
    serial_number: str = conf[CONF_SERIAL_NUMBER]
    scan_interval: timedelta = conf[CONF_SCAN_INTERVAL]
    scan_interval_inverter_info: timedelta | None = conf[
        CONF_SCAN_INTERVAL_INVERTER_INFO
    ]
    scan_interval_battery_info: timedelta | None = conf[CONF_SCAN_INTERVAL_BATTERY_INFO]
    scan_interval_battery_controller: timedelta | None = conf[
        CONF_SCAN_INTERVAL_BATTERY_CONTROLLER
    ]
    scan_interval_config: timedelta | None = conf[CONF_SCAN_INTERVAL_CONFIG]
    debug_mqtt: bool = conf[CONF_DEBUG_MQTT]
    hass.data[DOMAIN][DATA_CONFIG] = conf

    LOGGER.info(f"Setting up SAJ MQTT integration for inverter serial: {serial_number}")
    LOGGER.info(f"Scan interval realtime data: {scan_interval}")
    LOGGER.info(
        f"Scan interval inverter info data: {scan_interval_inverter_info or 'disabled'}"
    )
    LOGGER.info(
        f"Scan interval battery info data: {scan_interval_battery_info or 'disabled'}"
    )
    LOGGER.info(
        f"Scan interval controller data: {scan_interval_battery_controller or 'disabled'}"
    )
    LOGGER.info(f"Scan interval config data: {scan_interval_config or 'disabled'}")

    # Setup saj mqtt
    saj_mqtt = SajMqtt(hass, serial_number, debug_mqtt)
    await saj_mqtt.initialize()
    hass.data[DOMAIN][DATA_SAJMQTT] = saj_mqtt

    # Setup coordinators
    LOGGER.debug("Setting up coordinators")
    # Realtime data coordinator
    coordinator = SajMqttRealtimeDataCoordinator(hass, saj_mqtt, scan_interval)
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator
    # Inverter info data coordinators
    if scan_interval_inverter_info:
        coordinator_inverter_info = SajMqttInverterInfoDataCoordinator(
            hass, saj_mqtt, scan_interval_inverter_info
        )
        hass.data[DOMAIN][DATA_COORDINATOR_INVERTER_INFO] = coordinator_inverter_info
    # Battery info data coordinator
    if scan_interval_battery_info:
        coordinator_battery_info = SajMqttBatteryInfoDataCoordinator(
            hass, saj_mqtt, scan_interval_battery_info
        )
        hass.data[DOMAIN][DATA_COORDINATOR_BATTERY_INFO] = coordinator_battery_info
    # Battery controller data coordinators
    if scan_interval_battery_controller:
        coordinator_battery_controller = SajMqttBatteryControllerDataCoordinator(
            hass, saj_mqtt, scan_interval_battery_controller
        )
        hass.data[DOMAIN][
            DATA_COORDINATOR_BATTERY_CONTROLLER
        ] = coordinator_battery_controller
    # Config data coordinator
    if scan_interval_config:
        coordinator_config = SajMqttConfigDataCoordinator(
            hass, saj_mqtt, scan_interval_config
        )
        hass.data[DOMAIN][DATA_COORDINATOR_CONFIG] = coordinator_config

    # Register services (no need to await as function itself is not async)
    async_register_services(hass)

    # Wait some time go give the system time to subscribe
    # Without this, the initial data retrieval is not being picked up
    await asyncio.sleep(1)

    LOGGER.debug(f"Setting up plaforms: {[p.value for p in PLATFORMS]}")
    for plaform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, plaform, DOMAIN, {}, hass.data[DOMAIN][DATA_CONFIG]
            )
        )

    return True
