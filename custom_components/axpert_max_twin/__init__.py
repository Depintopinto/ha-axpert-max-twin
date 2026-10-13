"""Read-only integration for the captured Axpert MAX TWIN USB profile."""
from homeassistant.helpers.entity_registry import async_entries_for_config_entry, async_get as async_get_entity_registry

from .const import PLATFORMS
from .coordinator import AxpertCoordinator

OBSOLETE_ENERGY_ENTITY_KEYS = {
    'load_energy', 'load_energy_daily', 'load_energy_monthly', 'load_energy_yearly',
    'solar_energy', 'solar_energy_daily', 'solar_energy_monthly', 'solar_energy_yearly',
}


def _remove_obsolete_energy_entities(hass, entry):
    """Remove the retired 0.2.0 energy entities from this entry's registry."""
    registry = async_get_entity_registry(hass)
    obsolete_unique_ids = {f'{entry.entry_id}_{key}' for key in OBSOLETE_ENERGY_ENTITY_KEYS}
    for entity in async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == 'sensor' and entity.unique_id in obsolete_unique_ids:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass, entry):
    _remove_obsolete_energy_entities(hass, entry)
    coordinator = AxpertCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unloaded


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
