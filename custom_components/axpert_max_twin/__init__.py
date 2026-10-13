"""Read-only integration for the captured Axpert MAX TWIN USB profile."""
from .const import PLATFORMS
from .coordinator import AxpertCoordinator


async def async_setup_entry(hass, entry):
    coordinator = AxpertCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
