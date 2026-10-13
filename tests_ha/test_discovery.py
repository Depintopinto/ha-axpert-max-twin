"""Exercise HA's discovery path using the directory layout installed by HACS."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import custom_components
from homeassistant.core import HomeAssistant
from homeassistant import loader

DOMAIN = 'axpert_max_twin'
SOURCE = Path(__file__).resolve().parents[1] / 'custom_components' / DOMAIN


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_installed_component_is_in_add_integration_and_opens_form(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / 'custom_components' / DOMAIN
            shutil.copytree(SOURCE, installed, ignore=shutil.ignore_patterns('__pycache__'))
            hass = HomeAssistant(directory)
            try:
                loader.async_setup(hass)
                with patch.object(custom_components, '__path__', [str(installed.parent)]):
                    components = await loader.async_get_custom_components(hass)
                    self.assertIn(DOMAIN, components)
                    self.assertTrue(components[DOMAIN].config_flow)
                    self.assertIn(DOMAIN, await loader.async_get_config_flows(hass))
                    self.assertIn(DOMAIN, await loader.async_get_config_flows(hass, type_filter='device'))
                    descriptions = await loader.async_get_integration_descriptions(hass)
                    self.assertEqual(descriptions['custom']['integration'][DOMAIN]['name'], 'Axpert MAX TWIN')
                    platform = await components[DOMAIN].async_get_platform('config_flow')
                    flow = platform.AxpertConfigFlow()
                    flow.hass = hass
                    with patch('custom_components.axpert_max_twin.transport.HidrawTransport.poll') as poll:
                        result = await flow.async_step_user()
                        self.assertEqual(result['type'], 'form')
                        self.assertEqual(result['step_id'], 'user')
                        poll.assert_not_called()
            finally:
                await hass.async_stop(force=True)
