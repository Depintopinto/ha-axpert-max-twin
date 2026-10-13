from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .protocol import MODE_NAMES

SENSORS = (
    ('pv1_current', 'PV1 input current', 'A', SensorDeviceClass.CURRENT),
    ('pv1_voltage', 'PV1 input voltage', 'V', SensorDeviceClass.VOLTAGE),
    ('pv1_power', 'PV1 charging power', 'W', SensorDeviceClass.POWER),
    ('pv2_current', 'PV2 input current', 'A', SensorDeviceClass.CURRENT),
    ('pv2_voltage', 'PV2 input voltage', 'V', SensorDeviceClass.VOLTAGE),
    ('pv2_power', 'PV2 charging power', 'W', SensorDeviceClass.POWER),
    ('load_power', 'AC output active power', 'W', SensorDeviceClass.POWER),
    ('battery_voltage', 'Battery voltage', 'V', SensorDeviceClass.VOLTAGE),
    ('battery_charge_current', 'Battery charging current', 'A', SensorDeviceClass.CURRENT),
    ('battery_discharge_current', 'Battery discharge current', 'A', SensorDeviceClass.CURRENT),
    ('battery_soc', 'Battery reported capacity', '%', SensorDeviceClass.BATTERY),
    ('mode', 'Operating mode code', None, None),
    ('output_voltage', 'AC output voltage', 'V', SensorDeviceClass.VOLTAGE),
    ('output_frequency', 'AC output frequency', 'Hz', SensorDeviceClass.FREQUENCY),
    ('load_apparent_power', 'AC output apparent power', 'VA', SensorDeviceClass.APPARENT_POWER),
    ('load_percent', 'Inverter load', '%', None),
    ('output_current_calculated', 'AC output current (calculated)', 'A', SensorDeviceClass.CURRENT),
    ('power_factor_calculated', 'Power factor (calculated)', None, SensorDeviceClass.POWER_FACTOR),
    ('solar_power_total', 'Total solar charging power (calculated)', 'W', SensorDeviceClass.POWER),
    ('grid_voltage', 'Grid input voltage', 'V', SensorDeviceClass.VOLTAGE),
    ('grid_frequency', 'Grid input frequency', 'Hz', SensorDeviceClass.FREQUENCY),
    ('temperature', 'Inverter heat sink temperature', '°C', SensorDeviceClass.TEMPERATURE),
    ('operating_mode', 'Operating mode', None, SensorDeviceClass.ENUM),
    ('alarm_state', 'Alarms and faults', None, SensorDeviceClass.ENUM),
    ('warning_raw', 'Warning status (raw)', None, None),
    *((f'{source}_energy{suffix}', f'{label} energy{description} (estimated)', 'kWh', SensorDeviceClass.ENERGY)
      for source, label in (('load', 'AC output'), ('solar', 'Solar charging'))
      for suffix, description in (('', ''), ('_daily', ' today'), ('_monthly', ' this month'), ('_yearly', ' this year'))),
)

BASE_KEYS = {definition[0] for definition in SENSORS[:12]}
TEXT_KEYS = {'mode', 'operating_mode', 'alarm_state', 'warning_raw'}
CALCULATED_KEYS = {'output_current_calculated', 'power_factor_calculated', 'solar_power_total'}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(AxpertSensor(entry.runtime_data, entry, definition) for definition in SENSORS)


class AxpertSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, definition):
        super().__init__(coordinator)
        self.key, self._attr_name, self._attr_native_unit_of_measurement, self._attr_device_class = definition
        self._attr_unique_id = f'{entry.entry_id}_{self.key}'
        if self.key not in BASE_KEYS:
            self._attr_translation_key = self.key
            self._attr_name = None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)},
                                           name='Axpert MAX TWIN', manufacturer='Voltronic Power')
        if self.key not in TEXT_KEYS:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if '_energy' in self.key:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_suggested_display_precision = 3
        if self.key == 'operating_mode':
            self._attr_options = list(MODE_NAMES.values())
        if self.key == 'alarm_state':
            self._attr_options = ['normal', 'warning', 'fault', 'unknown']
        if self.key == 'warning_raw':
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False
        if self.key == 'power_factor_calculated':
            self._attr_suggested_display_precision = 3

    @property
    def available(self):
        return super().available and self.key in (self.coordinator.data or {})

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        group = ('solar' if self.key.startswith(('pv', 'solar')) else
                 'consumption' if self.key.startswith(('load', 'output', 'power_factor')) else 'inverter')
        kind = ('estimated' if '_energy' in self.key else
                'calculated' if self.key in CALCULATED_KEYS else 'reported')
        attributes = {'sensor_group': group, 'measurement_kind': kind}
        if self.key == 'output_current_calculated':
            attributes['assumption'] = 'single_phase_output'
        if self.key == 'alarm_state':
            data = self.coordinator.data or {}
            attributes.update(active_warnings=data.get('active_warnings', []),
                uninterpreted_positions=data.get('uninterpreted_warning_positions', []))
        return attributes
