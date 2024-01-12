"""DataUpdateCoordinators for SAJ MQTT integration."""
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

    async def _async_update_data(self) -> bytearray | None:
        """Fetch the data."""
        # Query inverter via mqtt for data
        LOGGER.debug("Fetching data")
        data = await self.saj_mqtt.query(0x4000, 0x100)
        return data
