"""Base entity: push updates from the speaker, device info, availability."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODELS
from .speaker import LibratoneSpeaker

_LOGGER = logging.getLogger(__name__)


class LibratoneEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, speaker: LibratoneSpeaker) -> None:
        self.speaker = speaker
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.serial or entry.entry_id)},
            manufacturer=MANUFACTURER,
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
        self._sync_device()
        self.async_write_ha_state()

    def _sync_device(self) -> None:
        """Keep firmware, model, MAC and the link to the speaker's web UI up to date."""
        if self.device_entry is None:
            return
        registry = dr.async_get(self.hass)
        dev = registry.async_get(self.device_entry.id)   # fresh, the entity's copy can be stale
        if dev is None:
            return
        spk = self.speaker
        changes: dict = {}
        if spk.version and dev.sw_version != spk.version:
            changes["sw_version"] = spk.version
        if spk.model:
            model = MODELS.get(spk.model, f"Libratone {spk.model}")
            if dev.model != model or dev.model_id != spk.model:
                changes.update(model=model, model_id=spk.model)
        url = f"http://{spk.host}/" if spk.host else None
        if url and dev.configuration_url != url:
            changes["configuration_url"] = url
        if spk.mac and (dr.CONNECTION_NETWORK_MAC, spk.mac) not in dev.connections:
            changes["merge_connections"] = {(dr.CONNECTION_NETWORK_MAC, spk.mac)}
        if not changes:
            return
        try:
            registry.async_update_device(dev.id, **changes)
        except Exception as err:  # e.g. a connection collision; cosmetic, never break the entity
            changes.pop("merge_connections", None)
            if changes:
                registry.async_update_device(dev.id, **changes)
            _LOGGER.debug("Device update for %s partly failed: %s", spk, err)
