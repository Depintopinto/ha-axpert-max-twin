import os
import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, DEFAULT_PATH


class AxpertConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            path = user_input['path']
            if not path.startswith('/dev/'):
                errors['base'] = 'invalid_path'
            else:
                canonical = await self.hass.async_add_executor_job(os.path.realpath, path)
                await self.async_set_unique_id(canonical)
                self._abort_if_unique_id_configured()
                # Setup probes the hardware; a transient USB outage can then retry automatically.
                return self.async_create_entry(title='Axpert MAX TWIN', data=user_input)
        return self.async_show_form(step_id='user', errors=errors, data_schema=vol.Schema({
            vol.Required('path', default=DEFAULT_PATH): str,
            vol.Required('interval', default=30): vol.All(vol.Coerce(int), vol.Range(min=15, max=3600)),
        }))
