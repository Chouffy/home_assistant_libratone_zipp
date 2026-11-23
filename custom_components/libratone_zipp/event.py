"""Event entity: a favorite was started (heart button on the speaker, the app, or Home Assistant).

Integrations don't act on this themselves; use it in automations, e.g. to replace a favorite slot with
a Home Assistant stream (only sensible if nobody relies on that slot from the app).
"""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .entity import LibratoneEntity

EVENT_TYPES = [f"favorite_{slot}" for slot in range(1, 6)]


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([FavoriteStartedEvent(entry, entry.runtime_data)])


class FavoriteStartedEvent(LibratoneEntity, EventEntity):
    _attr_translation_key = "favorite_started"
    _attr_icon = "mdi:heart-outline"
    _attr_event_types = EVENT_TYPES

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_favorite_started"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.speaker.add_favorite_listener(self._favorite_started))

    @callback
    def _favorite_started(self, slot: int, name: str | None, started_by_us: bool) -> None:
        self._trigger_event(
            f"favorite_{slot}",
            {"name": name, "started_by": "home_assistant" if started_by_us else "speaker_or_app"},
        )
        self.async_write_ha_state()
