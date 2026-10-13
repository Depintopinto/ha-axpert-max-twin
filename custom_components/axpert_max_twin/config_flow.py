import os
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_PATH, DEFAULT_INTERVAL, MIN_INTERVAL


def interval_schema(default):
    return vol.Schema({vol.Required('interval', default=default):
                       vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=3600))})


class AxpertConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AxpertOptionsFlow()

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
            vol.Required('interval', default=DEFAULT_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=3600)),
        }))


class AxpertOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        default = self.config_entry.options.get('interval',
                    self.config_entry.data.get('interval', DEFAULT_INTERVAL))
        schema = interval_schema(default)
        errors = {}
        if user_input is not None:
            try:
                validated = schema(user_input)
            except vol.Invalid:
                errors['base'] = 'invalid_interval'
            else:
                return self.async_create_entry(title='', data=validated)
        return self.async_show_form(step_id='init', data_schema=schema, errors=errors)
