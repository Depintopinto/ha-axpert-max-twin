from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import EntityCategory

from .const import DOMAIN

SENSORS = (
    ('pv1_current', 'Fotovoltaica · Corriente PV1', 'A', SensorDeviceClass.CURRENT),
    ('pv1_voltage', 'Fotovoltaica · Tensión PV1', 'V', SensorDeviceClass.VOLTAGE),
    ('pv1_power', 'Fotovoltaica · Potencia de carga PV1', 'W', SensorDeviceClass.POWER),
    ('pv2_current', 'Fotovoltaica · Corriente PV2', 'A', SensorDeviceClass.CURRENT),
    ('pv2_voltage', 'Fotovoltaica · Tensión PV2', 'V', SensorDeviceClass.VOLTAGE),
    ('pv2_power', 'Fotovoltaica · Potencia de carga PV2', 'W', SensorDeviceClass.POWER),
    ('load_power', 'Salida Red · Potencia activa AC', 'W', SensorDeviceClass.POWER),
    ('battery_voltage', 'Batería · Tensión', 'V', SensorDeviceClass.VOLTAGE),
    ('battery_charge_current', 'Batería · Corriente de carga', 'A', SensorDeviceClass.CURRENT),
    ('battery_discharge_current', 'Batería · Corriente de descarga', 'A', SensorDeviceClass.CURRENT),
    ('battery_soc', 'Batería · Nivel comunicado', '%', SensorDeviceClass.BATTERY),
    ('mode', 'General · Código de modo original', None, None),
    ('output_voltage', 'Salida Red · Tensión AC', 'V', SensorDeviceClass.VOLTAGE),
    ('output_frequency', 'Salida Red · Frecuencia AC', 'Hz', SensorDeviceClass.FREQUENCY),
    ('load_apparent_power', 'Salida Red · Potencia aparente AC', 'VA', SensorDeviceClass.APPARENT_POWER),
    ('load_percent', 'Salida Red · Porcentaje de carga', '%', None),
    ('output_current_calculated', 'Salida Red · Corriente calculada', 'A', SensorDeviceClass.CURRENT),
    ('power_factor_calculated', 'Salida Red · Factor de potencia calculado', None, SensorDeviceClass.POWER_FACTOR),
    ('solar_power_total', 'Fotovoltaica · Potencia total calculada', 'W', SensorDeviceClass.POWER),
    ('grid_voltage', 'Entrada Red · Tensión', 'V', SensorDeviceClass.VOLTAGE),
    ('grid_frequency', 'Entrada Red · Frecuencia', 'Hz', SensorDeviceClass.FREQUENCY),
    ('temperature', 'General · Temperatura del disipador', '°C', SensorDeviceClass.TEMPERATURE),
    ('operating_mode', 'General · Modo de funcionamiento', None, SensorDeviceClass.ENUM),
    ('alarm_state', 'General · Estado de alarmas y errores', None, SensorDeviceClass.ENUM),
    ('warning_raw', 'General · Trama original de avisos', None, None),
)

TEXT_KEYS = {'mode', 'operating_mode', 'alarm_state', 'warning_raw'}
CALCULATED_KEYS = {'output_current_calculated', 'power_factor_calculated', 'solar_power_total'}
MODE_LABELS = {'power_on': 'Encendido', 'standby': 'En espera', 'line': 'Red',
               'battery': 'Batería', 'fault': 'Fallo', 'shutdown': 'Apagado',
               'charge': 'Carga', 'bypass': 'Bypass', 'eco': 'Eco'}
ALARM_LABELS = {'normal': 'Sin avisos', 'warning': 'Aviso', 'fault': 'Fallo', 'unknown': 'Sin clasificar'}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(AxpertSensor(entry.runtime_data, entry, definition) for definition in SENSORS)


class AxpertSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, definition):
        super().__init__(coordinator)
        self.key, self._attr_name, self._attr_native_unit_of_measurement, self._attr_device_class = definition
        self._attr_unique_id = f'{entry.entry_id}_{self.key}'
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)},
                                           name='Axpert MAX TWIN', manufacturer='Voltronic Power')
        if self.key not in TEXT_KEYS:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if self.key == 'operating_mode':
            self._attr_options = list(MODE_LABELS.values())
        if self.key == 'alarm_state':
            self._attr_options = list(ALARM_LABELS.values())
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
        value = (self.coordinator.data or {}).get(self.key)
        if self.key == 'operating_mode':
            return MODE_LABELS.get(value, value)
        if self.key == 'alarm_state':
            return ALARM_LABELS.get(value, value)
        return value

    @property
    def extra_state_attributes(self):
        group = ('Fotovoltaica' if self.key.startswith(('pv', 'solar')) else
                 'Salida Red' if self.key.startswith(('load', 'output', 'power_factor')) else
                 'Entrada Red' if self.key.startswith('grid_') else
                 'Batería' if self.key.startswith('battery_') else 'General')
        kind = 'calculated' if self.key in CALCULATED_KEYS else 'reported'
        attributes = {'sensor_group': group, 'measurement_kind': kind}
        if self.key == 'output_current_calculated':
            attributes['assumption'] = 'single_phase_output'
        if self.key == 'alarm_state':
            data = self.coordinator.data or {}
            attributes.update(active_warnings=data.get('active_warnings', []),
                uninterpreted_positions=data.get('uninterpreted_warning_positions', []))
        return attributes
