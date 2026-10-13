"""Persistent trapezoidal energy estimates. No samples are invented across outages."""
from datetime import datetime, time, timedelta, timezone
import math

SOURCES = {'load': 'load_power', 'solar': 'solar_power_total'}
PERIODS = ('daily', 'monthly', 'yearly')


def period_ids(moment, zone):
    local = moment.astimezone(zone)
    return {'daily': local.strftime('%Y-%m-%d'), 'monthly': local.strftime('%Y-%m'),
            'yearly': local.strftime('%Y')}


class EnergyLedger:
    def __init__(self, zone=timezone.utc, stored=None):
        self.zone = zone
        self.previous = {}
        self.counters = {source: {'total': 0.0, **dict.fromkeys(PERIODS, 0.0), 'period_ids': {}}
                         for source in SOURCES}
        if stored is not None:
            if not isinstance(stored, dict) or stored.get('schema') != 1:
                raise ValueError('Unsupported stored energy schema')
            if not isinstance(stored.get('counters'), dict) or any(source not in stored['counters'] for source in SOURCES):
                raise ValueError('Missing stored energy counters')
            for source in SOURCES:
                item = stored['counters'][source]
                if not isinstance(item, dict) or any(key not in item for key in ('total', *PERIODS, 'period_ids')):
                    raise ValueError('Incomplete stored energy counter')
                for key in ('total', *PERIODS):
                    value = item[key]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        raise ValueError('Invalid stored energy counter')
                if not isinstance(item['period_ids'], dict) or any(not isinstance(v, str) for v in item['period_ids'].values()):
                    raise ValueError('Invalid stored energy periods')
                self.counters[source] = {key: item[key] for key in ('total', *PERIODS)}
                self.counters[source]['period_ids'] = dict(item['period_ids'])

    def break_continuity(self):
        self.previous.clear()

    def _roll_periods(self, counters, moment):
        identifiers = period_ids(moment, self.zone)
        for period, identifier in identifiers.items():
            if counters['period_ids'].get(period) != identifier:
                counters[period] = 0.0
        counters['period_ids'] = identifiers

    def _add_segment(self, counters, start, end, start_power, end_power):
        # Split at local midnight (including month/year boundaries and DST days).
        duration = (end-start).total_seconds()
        cursor = start
        while cursor < end:
            local = cursor.astimezone(self.zone)
            midnight = datetime.combine(local.date()+timedelta(days=1), time.min,
                                        self.zone).astimezone(timezone.utc)
            stop = min(end, midnight)
            seconds = (stop-cursor).total_seconds()
            p0 = start_power + (end_power-start_power) * ((cursor-start).total_seconds()/duration)
            p1 = start_power + (end_power-start_power) * ((stop-start).total_seconds()/duration)
            amount = (p0+p1)/2 * seconds / 3_600_000
            self._roll_periods(counters, cursor)
            counters['total'] += amount
            for period in PERIODS:
                counters[period] += amount
            cursor = stop
        self._roll_periods(counters, end)

    def update(self, data, moment, max_gap):
        if moment.tzinfo is None:
            raise ValueError('Energy timestamps must be timezone-aware')
        moment = moment.astimezone(timezone.utc)
        values = {}
        for source, field in SOURCES.items():
            counters = self.counters[source]
            power = data.get(field)
            previous = self.previous.pop(source, None)
            if power is None or not math.isfinite(power) or power < 0:
                self._roll_periods(counters, moment)
                continue
            if previous is not None:
                start, start_power = previous
                seconds = (moment-start).total_seconds()
                if 0 < seconds <= max_gap:
                    self._add_segment(counters, start, moment, start_power, power)
            self._roll_periods(counters, moment)
            self.previous[source] = (moment, power)
            values[f'{source}_energy'] = round(counters['total'], 6)
            for period in PERIODS:
                values[f'{source}_energy_{period}'] = round(counters[period], 6)
        return values

    def serialize(self):
        return {'schema': 1, 'counters': {source: {**counter, 'period_ids': dict(counter['period_ids'])}
                                        for source, counter in self.counters.items()}}
