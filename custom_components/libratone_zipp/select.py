"""Select entities: room placement (the app's 'FullRoom' setting) and sound mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .const import COLOR_CODES_BY_NAME, COLORS
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    spk = entry.runtime_data
    async_add_entities([RoomPlacementSelect(entry, spk), ChannelSelect(entry, spk), SaveFavoriteSelect(entry, spk),
                        ColorSelect(entry, spk)])


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


class SaveFavoriteSelect(LibratoneEntity, SelectEntity):
    """The app's '+': pick a slot to store the radio station that is playing now. Always shows no selection."""

    _attr_translation_key = "save_favorite"
    _attr_icon = "mdi:star-plus-outline"

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_save_favorite"

    @property
    def available(self) -> bool:
        return super().available and bool(self.speaker.channels) and self.speaker.current_station() is not None

    @property
    def options(self) -> list[str]:
        return self.speaker.favorite_names or ["1", "2", "3", "4", "5"]

    @property
    def current_option(self) -> str | None:
        return None

    async def async_select_option(self, option: str) -> None:
        slot = int(option.split(":", 1)[0])
        if not self.speaker.save_favorite(slot):
            raise ServiceValidationError(f"{self.speaker.display_name} isn't playing a radio station")


class ColorSelect(LibratoneEntity, SelectEntity):
    """The speaker's color as stored on the speaker (the app shows it; it can't change the fabric, obviously)."""

    _attr_translation_key = "color"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = [name for name, _hex in COLORS.values()]

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_color_select"

    @property
    def current_option(self) -> str | None:
        return COLORS.get(self.speaker.color or "", (None, None))[0]

    @property
    def extra_state_attributes(self) -> dict:
        return {"color_code": self.speaker.color, "hex": COLORS.get(self.speaker.color or "", (None, None))[1]}

    async def async_select_option(self, option: str) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")
        self.speaker.set_color(COLOR_CODES_BY_NAME[option])
