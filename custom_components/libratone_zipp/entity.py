"""Base entity: push updates from the speaker, device info, availability."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .speaker import LibratoneSpeaker


class LibratoneEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, speaker: LibratoneSpeaker) -> None:
        self.speaker = speaker
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.serial or entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Zipp",
            name=entry.title or speaker.display_name,
            serial_number=speaker.serial,
        )

    @property
    def available(self) -> bool:
        return self.speaker.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.speaker.add_listener(self._handle_update))
        self._handle_update()

    def _handle_update(self) -> None:
        if self.hass is None:
            return
        version = self.speaker.version
        if version and self.device_entry and self.device_entry.sw_version != version:
            dr.async_get(self.hass).async_update_device(self.device_entry.id, sw_version=version)
        self.async_write_ha_state()
