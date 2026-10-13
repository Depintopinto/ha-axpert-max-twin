from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_INTERVAL
from .protocol import ProtocolError
from .transport import HidrawTransport


class AxpertCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         config_entry=entry, update_interval=timedelta(seconds=entry.options.get(
                             'interval', entry.data.get('interval', DEFAULT_INTERVAL))))
        self.transport = HidrawTransport(entry.data['path'])

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self.transport.poll)
        except (OSError, ProtocolError) as err:
            raise UpdateFailed(str(err)) from err
