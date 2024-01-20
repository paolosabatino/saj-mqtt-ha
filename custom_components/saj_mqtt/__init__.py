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
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_NUMBER,
    DATA_CONFIG,
    DATA_COORDINATOR,
    DATA_SAJMQTT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import SajMqttCoordinator
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
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up using yaml config file."""
    hass.data.setdefault(DOMAIN, {})

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
    LOGGER.info(
        f"Setting up SAJ MQTT integration - inverter serial: {serial_number} - scan interval: {scan_interval}"
    )
    hass.data[DOMAIN][DATA_CONFIG] = conf

    # Setup saj mqtt
    saj_mqtt = SajMqtt(hass, serial_number)
    await saj_mqtt.initialize()
    hass.data[DOMAIN][DATA_SAJMQTT] = saj_mqtt

    # Setup coordinator
    LOGGER.debug("Setting up coordinator")
    coordinator = SajMqttCoordinator(hass, saj_mqtt, scan_interval)
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator

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
