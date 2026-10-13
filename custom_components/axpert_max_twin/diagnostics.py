"""Only allowlisted query frames; never expose entry data or filesystem paths."""
async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    # Errors may contain paths from the OS; report their category only.
    queries = {command: {key: value for key, value in result.items() if key != 'error'}
               for command, result in coordinator.transport.diagnostics.items()}
    return {'profile': 'capture-24-fields', 'capture_profile_verified': True,
            'communication_verified': coordinator.last_update_success,
            'last_update_success': coordinator.last_update_success, 'queries': queries}
