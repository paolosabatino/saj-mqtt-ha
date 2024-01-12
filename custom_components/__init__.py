"""The SAJ MQTT integration."""
from __future__ import annotations

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
    CONF_SCAN_INTERVAL_DEFAULT_IN_SECONDS,
    CONF_SERIAL_NUMBER,
    DATA_COORDINATOR,
    DATA_SAJMQTT,
    DOMAIN,
    LOGGER,
)
from .coordinator import SajMqttCoordinator
from .sajmqtt import SajMqtt

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=timedelta(seconds=CONF_SCAN_INTERVAL_DEFAULT_IN_SECONDS),
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

    if DOMAIN not in config or CONF_SERIAL_NUMBER not in config[DOMAIN]:
        LOGGER.error("SAJ MQTT integration is not configured correctly")
        return False

    # Get config data
    serial_number: str = config[DOMAIN].get(CONF_SERIAL_NUMBER)
    scan_interval: timedelta = (
        config[DOMAIN].get(CONF_SCAN_INTERVAL)
        if CONF_SCAN_INTERVAL in config[DOMAIN]
        else timedelta(seconds=CONF_SCAN_INTERVAL_DEFAULT_IN_SECONDS)
    )
    LOGGER.info(
        f"Setting up SAJ MQTT integration - inverter serial: {serial_number} - scan interval: {scan_interval}"
    )

    # Setup saj mqtt
    saj_mqtt = SajMqtt(hass, serial_number)
    await saj_mqtt.initialize()
    hass.data[DOMAIN][DATA_SAJMQTT] = saj_mqtt

    # Setup coordinator and load initial data
    LOGGER.debug("Setting up coordinator")
    coordinator = SajMqttCoordinator(hass, saj_mqtt, scan_interval)
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator

    LOGGER.debug("Setting up plaforms")
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    )

    hass.async_create_task(coordinator.async_refresh())

    return True
