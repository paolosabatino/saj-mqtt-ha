"""DataUpdateCoordinators for SAJ MQTT integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER
from .sajmqtt import SajMqtt
from .utils import log_hex


class SajMqttDataCoordinator(DataUpdateCoordinator):
    """SAJ MQTT data coordinator."""

    def __init__(
        self, hass: HomeAssistant, saj_mqtt: SajMqtt, scan_interval: timedelta
    ) -> None:
        """Set up the SajMqttDataCoordinator class."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.saj_mqtt = saj_mqtt
        self.data: bytearray | None = None


class SajMqttRealtimeDataCoordinator(SajMqttDataCoordinator):
    """SAJ MQTT realtime data coordinator."""

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the realtime data."""
        reg_start = 0x4000
        reg_count = 0x100  # 256 registers
        LOGGER.debug(
            f"Fetching realtime data at {log_hex(reg_start)}, length: {log_hex(reg_count)}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)


class SajMqttInverterInfoDataCoordinator(SajMqttDataCoordinator):
    """SAJ MQTT inverter info data coordinator."""

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the inverter info."""
        reg_start = 0x8F00
        reg_count = 0x1E  # 30 registers
        LOGGER.debug(
            f"Fetching inverter info at {log_hex(reg_start)}, length: {log_hex(reg_count)}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)


class SajMqttBatteryInfoDataCoordinator(SajMqttDataCoordinator):
    """SAJ MQTT battery info data coordinator."""

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the battery info."""
        reg_start = 0x8E00
        reg_count = 0x50  # 80 registers
        LOGGER.debug(
            f"Fetching battery info at {log_hex(reg_start)}, length: {log_hex(reg_count)}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)


class SajMqttBatteryControllerDataCoordinator(SajMqttDataCoordinator):
    """SAJ MQTT battery controller data coordinator."""

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the battery controller data."""
        reg_start = 0xA000
        reg_count = 0x24  # 36 registers
        LOGGER.debug(
            f"Fetching battery controller data at {log_hex(reg_start)}, length: {log_hex(reg_count)}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)


class SajMqttConfigDataCoordinator(SajMqttDataCoordinator):
    """SAJ MQTT config data coordinator."""

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the config data."""
        reg_start = 0x3247
        reg_count = 0x2E  # 46 registers
        LOGGER.debug(
            f"Fetching config data at {log_hex(reg_start)}, length: {log_hex(reg_count)}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)
