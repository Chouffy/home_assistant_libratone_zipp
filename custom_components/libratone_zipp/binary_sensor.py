"""Muted (read-only): the speaker mutes itself when its touch panel is held."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([MutedBinarySensor(entry, entry.runtime_data)])


class MutedBinarySensor(LibratoneEntity, BinarySensorEntity):
    _attr_translation_key = "muted"
    _attr_icon = "mdi:volume-off"

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_muted"

    @property
    def is_on(self) -> bool | None:
        return self.speaker.muted
