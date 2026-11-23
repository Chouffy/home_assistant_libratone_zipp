"""Sleep timer as a number entity (minutes, 0 = off). Shows the remaining time."""
from __future__ import annotations

import math

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SleepTimerNumber(entry, entry.runtime_data)])


class SleepTimerNumber(LibratoneEntity, NumberEntity):
    _attr_translation_key = "sleep_timer"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_sleep_timer"

    @property
    def native_value(self) -> int:
        """Remaining minutes, rounded up; 0 = no timer."""
        return math.ceil(self.speaker.timer / 60) if self.speaker.timer else 0

    async def async_set_native_value(self, value: float) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")
        if value <= 0:
            self.speaker.cancel_sleep_timer()
        else:
            self.speaker.set_sleep_timer(round(value * 60))
