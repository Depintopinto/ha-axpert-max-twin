from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

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
)


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
        if self.key != 'mode':
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self):
        return super().available and self.key in (self.coordinator.data or {})

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
