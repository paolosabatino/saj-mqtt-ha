"""DataUpdateCoordinators for SAJ MQTT integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER
from .sajmqtt import SajMqtt


class SajMqttCoordinator(DataUpdateCoordinator):
    """SAJ MQTT data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, saj_mqtt: SajMqtt, scan_interval: timedelta
    ) -> None:
        """Set up the SajMqttCoordinator class."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.saj_mqtt = saj_mqtt

        self.inverter_info: bytearray | None = None
        self.battery_info: bytearray | None = None
        self.battery_controller_data: bytearray | None = None
        self.realtime_data: bytearray | None = None

    async def _async_update_data(self) -> dict[str, bytearray | None] | None:
        """Fetch the data."""
        LOGGER.debug("Fetching data")
        # Fetch inverter info only once
        if self.inverter_info is None:
            self.inverter_info = await self._fetch_inverter_info()

        # Fetch battery info only once
        if self.battery_info is None:
            self.battery_info = await self._fetch_battery_info()

        # Fetch battery controller data
        self.battery_controller_data = await self._fetch_battery_controller_data()

        # Fetch realtime data
        self.realtime_data = await self._fetch_realtime_data()

        return {
            "inverter_info": self.inverter_info,
            "battery_info": self.battery_info,
            "battery_controller_data": self.battery_controller_data,
            "realtime_data": self.realtime_data,
        }

    async def _fetch_inverter_info(self) -> bytearray | None:
        """Fetch the inverter info."""
        reg_start = 0x8F00
        reg_count = 0x1E  # 30 registers
        LOGGER.debug(
            f"Fetching inverter info at {reg_start:04x}, length: {reg_count:02x}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)

    async def _fetch_battery_info(self) -> bytearray | None:
        """Fetch the battery info."""
        reg_start = 0x8E00
        reg_count = 0x50  # 80 registers
        LOGGER.debug(
            f"Fetching battery info at {reg_start:04x}, length: {reg_count:02x}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)

    async def _fetch_battery_controller_data(self) -> bytearray | None:
        """Fetch the battery controller data."""
        reg_start = 0xA000
        reg_count = 0x24  # 36 registers
        LOGGER.debug(
            f"Fetching battery controller data at {reg_start:04x}, length: {reg_count:02x}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)

    async def _fetch_realtime_data(self) -> bytearray | None:
        """Fetch the realtime data."""
        reg_start = 0x4000
        reg_count = 0x100  # 256 registers
        LOGGER.debug(
            f"Fetching realtime data at {reg_start:04x}, length: {reg_count:02x}"
        )
        return await self.saj_mqtt.read_registers(reg_start, reg_count)
