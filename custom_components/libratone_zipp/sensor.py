"""Battery sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([BatterySensor(entry, entry.runtime_data)])


class BatterySensor(LibratoneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_battery"

    @property
    def native_value(self) -> int | None:
        return self.speaker.battery
