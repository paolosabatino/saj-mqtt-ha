"""Handle SAJ MQTT Service calls."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_APP_MODE,
    DATA_SAJMQTT,
    DOMAIN,
    LOGGER,
    MODBUS_REG_APP_MODE,
    SERVICE_SET_APP_MODE,
    AppMode,
)
from .sajmqtt import SajMqtt


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for SAJ MQTT integration."""

    async def set_app_mode(call: ServiceCall) -> None:
        saj_mqtt: SajMqtt = hass.data[DOMAIN][DATA_SAJMQTT]
        app_mode = AppMode[call.data[ATTR_APP_MODE]].value
        saj_mqtt.write_register(MODBUS_REG_APP_MODE, app_mode)

    LOGGER.debug(f"Registering service: {SERVICE_SET_APP_MODE}")
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_APP_MODE,
        set_app_mode,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_APP_MODE): vol.All(
                        cv.string, vol.In([e.name for e in AppMode])
                    )
                }
            )
        ),
    )
