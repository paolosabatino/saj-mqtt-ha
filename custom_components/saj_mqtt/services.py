"""Handle SAJ MQTT Service calls."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_APP_MODE,
    ATTR_REGISTER,
    ATTR_REGISTER_VALUE,
    DATA_SAJMQTT,
    DOMAIN,
    LOGGER,
    MODBUS_REG_APP_MODE,
    SERVICE_SET_APP_MODE,
    SERVICE_WRITE_REGISTER,
    AppMode,
)
from .sajmqtt import SajMqtt


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for SAJ MQTT integration."""

    async def set_app_mode(call: ServiceCall) -> None:
        LOGGER.debug("Setting app mode")
        saj_mqtt: SajMqtt = hass.data[DOMAIN][DATA_SAJMQTT]
        app_mode = AppMode[call.data[ATTR_APP_MODE]].value
        await saj_mqtt.write_register(MODBUS_REG_APP_MODE, app_mode)

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

    async def write_register(call: ServiceCall) -> None:
        LOGGER.debug("Writing register")
        saj_mqtt: SajMqtt = hass.data[DOMAIN][DATA_SAJMQTT]
        attr_register: str = call.data[ATTR_REGISTER]
        attr_register_value: str = call.data[ATTR_REGISTER_VALUE]
        try:
            if attr_register.startswith("0x"):
                register = int(attr_register, 16)
            else:
                register = int(attr_register)
        except ValueError as e:
            LOGGER.error(f"Invalid register: {attr_register}")
            raise e
        try:
            if attr_register_value.startswith("0x"):
                value = int(attr_register_value, 16)
            else:
                value = int(attr_register_value)
        except ValueError as e:
            LOGGER.error(f"Invalid register value: {attr_register_value}")
            raise e
        # Write register
        await saj_mqtt.write_register(register, value)

    LOGGER.debug(f"Registering service: {SERVICE_WRITE_REGISTER}")
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        write_register,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_REGISTER): cv.string,
                    vol.Required(ATTR_REGISTER_VALUE): cv.string,
                }
            )
        ),
    )
