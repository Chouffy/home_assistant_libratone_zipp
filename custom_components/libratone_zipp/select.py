"""Select entities: room placement (the app's 'FullRoom' setting) and sound mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([RoomPlacementSelect(entry, entry.runtime_data), ChannelSelect(entry, entry.runtime_data)])


class RoomPlacementSelect(LibratoneEntity, SelectEntity):
    _attr_translation_key = "room_placement"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sofa-single"

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_room"

    @property
    def available(self) -> bool:
        return super().available and bool(self.speaker.rooms)

    @property
    def options(self) -> list[str]:
        return self.speaker.room_names

    @property
    def current_option(self) -> str | None:
        return self.speaker.room

    async def async_select_option(self, option: str) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")
        if not self.speaker.set_room(option):
            raise ServiceValidationError(f"Unknown room placement: {option}")


class ChannelSelect(LibratoneEntity, SelectEntity):
    """Which audio channel the speaker plays: both (stereo), left or right. Mostly useful when linked."""

    _attr_translation_key = "channel"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:speaker-multiple"
    _attr_options = ["stereo", "left", "right"]

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_channel"

    @property
    def current_option(self) -> str | None:
        return self.speaker.channel

    async def async_select_option(self, option: str) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")
        if not self.speaker.set_channel(option):
            raise ServiceValidationError(f"Unknown channel: {option}")
