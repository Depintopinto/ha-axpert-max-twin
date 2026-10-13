"""Read-only integration for the captured Axpert MAX TWIN USB profile."""
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from .const import PLATFORMS
from .coordinator import AxpertCoordinator


async def async_setup_entry(hass, entry):
    coordinator = AxpertCoordinator(hass, entry)
    await coordinator.async_restore_energy()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def async_save_on_shutdown(event):
        await coordinator.async_save_energy()

    entry.async_on_unload(hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_FINAL_WRITE, async_save_on_shutdown))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_save_energy()
    return unloaded


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
