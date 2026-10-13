"""Read-only integration for the captured Axpert MAX TWIN USB profile."""
from .const import PLATFORMS
from .coordinator import AxpertCoordinator


async def async_setup_entry(hass, entry):
    coordinator = AxpertCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
