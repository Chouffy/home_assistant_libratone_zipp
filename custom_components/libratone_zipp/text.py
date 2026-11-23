"""Speaker name (as shown in the app, AirPlay, Spotify Connect)."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SpeakerNameText(entry, entry.runtime_data)])


class SpeakerNameText(LibratoneEntity, TextEntity):
    """Renames the speaker itself (SET 90). Verified: NOTIFY 90 echo, LSSDP/AirPlay name follow."""

    _attr_translation_key = "speaker_name"
    _attr_icon = "mdi:rename-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 1
    _attr_native_max = 32

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_name"

    @property
    def native_value(self) -> str | None:
        return self.speaker.name

    async def async_set_value(self, value: str) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")
        self.speaker.set_name(value)
