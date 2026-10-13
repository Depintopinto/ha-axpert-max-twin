"""Tests against actual HA classes; run on Linux with Home Assistant installed."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from datetime import timedelta
import tempfile

from custom_components.axpert_max_twin import async_setup_entry, async_unload_entry
from custom_components.axpert_max_twin.config_flow import AxpertConfigFlow, AxpertOptionsFlow
from custom_components.axpert_max_twin.coordinator import AxpertCoordinator
from custom_components.axpert_max_twin.diagnostics import async_get_config_entry_diagnostics
from custom_components.axpert_max_twin.sensor import AxpertSensor, SENSORS
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.core import HomeAssistant


class HomeAssistantTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_and_unload(self):
        hass = SimpleNamespace(config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True)))
        entry = SimpleNamespace(entry_id='test', data={'path':'/dev/hidraw0','interval':30},
                                async_on_unload=MagicMock(), add_update_listener=MagicMock())
        with patch('custom_components.axpert_max_twin.AxpertCoordinator') as factory:
            coordinator = factory.return_value
            coordinator.async_config_entry_first_refresh = AsyncMock()
            self.assertTrue(await async_setup_entry(hass,entry))
            self.assertIs(entry.runtime_data,coordinator)
            coordinator.async_config_entry_first_refresh.assert_awaited_once()
            hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry,['sensor'])
            self.assertTrue(await async_unload_entry(hass,entry))

    async def test_interval_options_accept_five_and_reject_four(self):
        entry = SimpleNamespace(options={},data={'interval':30})
        with patch.object(AxpertOptionsFlow,'config_entry',new_callable=PropertyMock,return_value=entry):
            flow=AxpertOptionsFlow()
            form=await flow.async_step_init()
            self.assertEqual(form['data_schema']({})['interval'],30)
            result=await flow.async_step_init({'interval':5})
            self.assertEqual(result['type'],'create_entry')
            self.assertEqual(result['data'],{'interval':5})
            invalid=await flow.async_step_init({'interval':4})
            self.assertEqual(invalid['type'],'form')
            self.assertEqual(invalid['errors']['base'],'invalid_interval')

    async def test_coordinator_uses_saved_interval_option(self):
        with tempfile.TemporaryDirectory() as directory:
            hass=HomeAssistant(directory)
            entry=MagicMock()
            entry.data={'path':'/dev/hidraw0','interval':30}
            entry.options={'interval':5}
            try:
                coordinator=AxpertCoordinator(hass,entry)
                self.assertEqual(coordinator.update_interval,timedelta(seconds=5))
                entry.options={}
                original=AxpertCoordinator(hass,entry)
                self.assertEqual(original.update_interval,timedelta(seconds=30))
            finally:
                await hass.async_stop(force=True)

    async def test_executor_and_failure(self):
        # Call the real coordinator update method with executor behavior, not USB hardware.
        async def executor(function): return function()
        coordinator = SimpleNamespace(hass=SimpleNamespace(async_add_executor_job=executor),
                                      transport=SimpleNamespace(poll=MagicMock(return_value={'load_power':2696})))
        self.assertEqual(await AxpertCoordinator._async_update_data(coordinator),{'load_power':2696})
        coordinator.transport.poll.side_effect = TimeoutError('QPIGS: no USB input')
        with self.assertRaises(UpdateFailed):
            await AxpertCoordinator._async_update_data(coordinator)

    async def test_optional_sensor_unavailable(self):
        coordinator = SimpleNamespace(data={'load_power':2696},last_update_success=True)
        entry = SimpleNamespace(entry_id='test')
        load = AxpertSensor(coordinator,entry,next(d for d in SENSORS if d[0]=='load_power'))
        pv2 = AxpertSensor(coordinator,entry,next(d for d in SENSORS if d[0]=='pv2_power'))
        self.assertTrue(load.available)
        self.assertEqual(load.native_value,2696)
        self.assertFalse(pv2.available)
        coordinator.last_update_success=False
        self.assertFalse(load.available)

    async def test_diagnostics_redacts_error_paths(self):
        entry=SimpleNamespace(runtime_data=SimpleNamespace(last_update_success=False,
            transport=SimpleNamespace(diagnostics={'QPIGS':{'status':'PermissionError','error':'/private/path'}})))
        result=await async_get_config_entry_diagnostics(None,entry)
        self.assertNotIn('/private/path',str(result))
        self.assertEqual(result['queries']['QPIGS']['status'],'PermissionError')

    async def test_config_form_and_duplicate(self):
        flow=AxpertConfigFlow()
        flow.hass=MagicMock()
        flow.hass.async_add_executor_job=AsyncMock(return_value='/dev/hidraw0')
        flow.async_show_form=MagicMock(return_value={'type':'form'})
        self.assertEqual(await flow.async_step_user(),{'type':'form'})
        flow.async_set_unique_id=AsyncMock()
        flow._abort_if_unique_id_configured=MagicMock()
        flow.async_create_entry=MagicMock(return_value={'type':'create_entry'})
        self.assertEqual(await flow.async_step_user({'path':'/dev/hidraw0','interval':30}),{'type':'create_entry'})
        flow._abort_if_unique_id_configured.assert_called_once()
