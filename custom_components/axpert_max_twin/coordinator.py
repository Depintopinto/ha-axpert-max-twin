from datetime import timedelta
import logging
import time
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULT_INTERVAL
from .protocol import ProtocolError, derived
from .energy import EnergyLedger
from .transport import HidrawTransport


class AxpertCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         config_entry=entry, update_interval=timedelta(seconds=entry.options.get(
                             'interval', entry.data.get('interval', DEFAULT_INTERVAL))))
        self.transport = HidrawTransport(entry.data['path'])
        self.energy_store = Store(hass, 1, f'{DOMAIN}.{entry.entry_id}.energy')
        self.ledger = EnergyLedger(ZoneInfo(hass.config.time_zone))
        self.last_energy_save = time.monotonic()

    async def async_restore_energy(self):
        stored = await self.energy_store.async_load()
        self.ledger = EnergyLedger(ZoneInfo(self.hass.config.time_zone), stored)

    async def async_save_energy(self):
        await self.energy_store.async_save(self.ledger.serialize())
        self.last_energy_save = time.monotonic()

    async def _async_update_data(self):
        try:
            data = derived(await self.hass.async_add_executor_job(self.transport.poll))
        except (OSError, ProtocolError) as err:
            self.ledger.break_continuity()
            raise UpdateFailed(str(err)) from err
        data.update(self.ledger.update(data, dt_util.utcnow(),
                    max_gap=max(15, 3*self.update_interval.total_seconds())))
        if time.monotonic()-self.last_energy_save >= 60:
            await self.async_save_energy()
        return data
