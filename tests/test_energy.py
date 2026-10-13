from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import unittest
from load_component import load

e=load('energy')
START=datetime(2026,10,13,12,tzinfo=timezone.utc)


class EnergyTests(unittest.TestCase):
    def test_actual_elapsed_time_trapezoidal(self):
        ledger=e.EnergyLedger()
        ledger.update({'load_power':1000},START,4000)
        values=ledger.update({'load_power':3000},START+timedelta(hours=1),4000)
        self.assertEqual(values['load_energy'],2)
        self.assertEqual(values['load_energy_daily'],2)

    def test_five_second_interval(self):
        ledger=e.EnergyLedger()
        ledger.update({'load_power':2000},START,15)
        values=ledger.update({'load_power':2000},START+timedelta(seconds=5),15)
        self.assertAlmostEqual(values['load_energy'],0.002778,places=6)

    def test_failure_and_restart_do_not_bridge_gap(self):
        ledger=e.EnergyLedger()
        ledger.update({'load_power':1000},START,15)
        ledger.update({'load_power':1000},START+timedelta(seconds=5),15)
        before=ledger.counters['load']['total']
        ledger.break_continuity()
        ledger.update({'load_power':1000},START+timedelta(seconds=10),15)
        self.assertEqual(ledger.counters['load']['total'],before)
        restored=e.EnergyLedger(stored=ledger.serialize())
        restored.update({'load_power':1000},START+timedelta(hours=2),15)
        self.assertEqual(restored.counters['load']['total'],before)
        restored.update({'load_power':1000},START+timedelta(hours=2,seconds=5),15)
        self.assertGreater(restored.counters['load']['total'],before)

    def test_long_gap_and_backwards_time(self):
        ledger=e.EnergyLedger()
        ledger.update({'load_power':1000},START,15)
        self.assertEqual(ledger.update({'load_power':1000},START+timedelta(seconds=60),15)['load_energy'],0)
        self.assertEqual(ledger.update({'load_power':1000},START+timedelta(seconds=59),15)['load_energy'],0)

    def test_missing_solar_channel_only_breaks_solar(self):
        ledger=e.EnergyLedger()
        data={'load_power':1000,'solar_power_total':2000}
        ledger.update(data,START,15)
        missing=ledger.update({'load_power':1000},START+timedelta(seconds=5),15)
        self.assertNotIn('solar_energy',missing)
        self.assertGreater(missing['load_energy'],0)
        returned=ledger.update(data,START+timedelta(seconds=10),15)
        self.assertEqual(returned['solar_energy'],0)

    def test_split_at_midnight_month_and_year(self):
        ledger=e.EnergyLedger()
        start=datetime(2026,12,31,23,59,30,tzinfo=timezone.utc)
        ledger.update({'load_power':2000},start,90)
        values=ledger.update({'load_power':2000},start+timedelta(seconds=60),90)
        self.assertAlmostEqual(values['load_energy'],0.033333,places=6)
        for period in e.PERIODS:
            self.assertAlmostEqual(values[f'load_energy_{period}'],0.016667,places=6)

    def test_dst_days_use_actual_utc_duration(self):
        zone=ZoneInfo('Europe/Madrid')
        for start,end,hours in (
            (datetime(2026,3,28,23,tzinfo=timezone.utc),datetime(2026,3,29,22,tzinfo=timezone.utc),23),
            (datetime(2026,10,24,22,tzinfo=timezone.utc),datetime(2026,10,25,23,tzinfo=timezone.utc),25)):
            ledger=e.EnergyLedger(zone)
            ledger.update({'load_power':1000},start,100000)
            values=ledger.update({'load_power':1000},end,100000)
            self.assertEqual(values['load_energy'],hours)
            self.assertEqual(values['load_energy_daily'],0)

    def test_bad_storage_rejected_instead_of_silently_resetting(self):
        for stored in ({},{'schema':1},{'schema':2}):
            with self.assertRaises(ValueError): e.EnergyLedger(stored=stored)
        for value in (-1,float('nan'),True):
            stored=e.EnergyLedger().serialize()
            stored['counters']['load']['total']=value
            with self.assertRaises(ValueError): e.EnergyLedger(stored=stored)

    def test_invalid_power_and_naive_time(self):
        ledger=e.EnergyLedger()
        for power in (-1,float('nan'),float('inf'),None):
            self.assertNotIn('load_energy',ledger.update({'load_power':power},START,15))
        with self.assertRaises(ValueError): ledger.update({'load_power':1000},datetime(2026,1,1),15)
