"""Handle SAJ MQTT Service calls."""
from __future__ import annotations

from struct import unpack_from

import voluptuous as vol

from homeassistant import core
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_APP_MODE,
    ATTR_REGISTER,
    ATTR_REGISTER_FORMAT,
    ATTR_REGISTER_SIZE,
    ATTR_REGISTER_VALUE,
    DATA_SAJMQTT,
    DOMAIN,
    LOGGER,
    MODBUS_REG_APP_MODE,
    SERVICE_READ_REGISTER,
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
        # Validate input
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

    async def read_register(call: ServiceCall) -> core.ServiceResponse:
        LOGGER.debug("Reading register")
        saj_mqtt: SajMqtt = hass.data[DOMAIN][DATA_SAJMQTT]
        attr_register: str = call.data[ATTR_REGISTER]
        attr_register_size: str = call.data[ATTR_REGISTER_SIZE]
        attr_register_format: str | None = call.data[ATTR_REGISTER_FORMAT]
        # Validate input
        try:
            if attr_register.startswith("0x"):
                register_start = int(attr_register, 16)
            else:
                register_start = int(attr_register)
        except ValueError as e:
            LOGGER.error(f"Invalid register: {attr_register}")
            raise e
        try:
            if attr_register_size.startswith("0x"):
                register_size = int(attr_register_size, 16)
            else:
                register_size = int(attr_register_size)
        except ValueError as e:
            LOGGER.error(f"Invalid register size: {attr_register_size}")
            raise e
        if attr_register_format and not attr_register_format.startswith(">"):
            msg = f"Invalid register format: {attr_register_format}"
            LOGGER.error(msg)
            raise ValueError(msg)
        # Read register
        content = await saj_mqtt.read_registers(register_start, register_size)
        # Return response (format if needed, otherwise return bytes)
        if attr_register_format:
            (result,) = unpack_from(attr_register_format, content, 0)
            return {"value": str(result)}
        return {"value": ":".join(f"{b:02x}" for b in content)}

    LOGGER.debug(f"Registering service: {SERVICE_READ_REGISTER}")
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_REGISTER,
        read_register,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Required(ATTR_REGISTER): cv.string,
                    vol.Required(ATTR_REGISTER_SIZE): cv.string,
                    vol.Optional(ATTR_REGISTER_FORMAT, default=None): vol.Any(
                        cv.string, None
                    ),
                }
            )
        ),
        supports_response=SupportsResponse.ONLY,
    )
