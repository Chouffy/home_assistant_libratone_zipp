"""Media player entity for Libratone speakers."""
from __future__ import annotations

import voluptuous as vol


from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LibratoneConfigEntry, entity_unique_id, legacy_unique_id
from .entity import LibratoneEntity
from .speaker import LibratoneSpeaker

FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.GROUPING
)

STATE_MAP = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "buffering": MediaPlayerState.BUFFERING,
    "stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LibratoneMediaPlayer(entry, entry.runtime_data)])
    entity_platform.async_get_current_platform().async_register_entity_service(
        "save_favorite",
        {vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=5))},
        "async_save_favorite",
    )


class LibratoneMediaPlayer(LibratoneEntity, MediaPlayerEntity, RestoreEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = FEATURES
    _attr_media_content_type = MediaType.MUSIC
    _attr_volume_step = 0.02

    def __init__(self, entry: LibratoneConfigEntry, speaker: LibratoneSpeaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = (
            entity_unique_id(speaker.serial) if speaker.serial else legacy_unique_id(entry.data["host"])
        )

    async def async_added_to_hass(self) -> None:
        self.speaker.entity_id = self.entity_id
        # Group state is only pushed on change, so seed it from before the restart.
        # Any real group notification overrides it.
        if self.speaker.group_link_id is None and (last := await self.async_get_last_state()):
            attrs = last.attributes  # libratone_* names are from integration versions <= 4.x
            self.speaker.group_link_id = attrs.get("group_link_id") or attrs.get("libratone_group_link_id")
            self.speaker.group_role = attrs.get("group_role") or attrs.get("libratone_group_role")
        await super().async_added_to_hass()
        for other in self._hub.speakers:
            if other is not self.speaker:
                other.notify()

    # ------------------------------------------------------------------ helpers
    @property
    def _hub(self):
        return self.speaker.hub

    @property
    def _media_source(self) -> LibratoneSpeaker:
        """A group slave reports no media; show (and control) its master instead."""
        if self.speaker.group_link_id:
            master = self._hub.group_master(self.speaker)
            if master is not None:
                return master
        return self.speaker

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> MediaPlayerState | None:
        spk = self.speaker
        if spk.power is None and spk.play_status is None:
            return None
        if spk.is_sleeping:
            return MediaPlayerState.OFF
        status = self._media_source.effective_status
        return STATE_MAP.get(status, MediaPlayerState.ON) if status else MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        return None if self.speaker.volume is None else self.speaker.volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        return self.speaker.muted

    @property
    def media_title(self) -> str | None:
        return self._media_source.media_title

    @property
    def media_artist(self) -> str | None:
        return self._media_source.media_artist

    @property
    def media_album_name(self) -> str | None:
        return self._media_source.media_album

    @property
    def media_playlist(self) -> str | None:
        return self._media_source.media_playlist

    @property
    def media_image_url(self) -> str | None:
        return self._media_source.media_image_url

    @property
    def media_content_id(self) -> str | None:
        return self._media_source.media_content_id

    @property
    def source(self) -> str | None:
        return self._media_source.source

    @property
    def source_list(self) -> list[str] | None:
        return self.speaker.favorite_names or None

    @property
    def sound_mode(self) -> str | None:
        return self.speaker.voicing

    @property
    def sound_mode_list(self) -> list[str] | None:
        return self.speaker.voicing_names or None

    @property
    def group_members(self) -> list[str] | None:
        members = self._hub.group_members(self.speaker)
        ids = [m.entity_id for m in members if m.entity_id]
        return ids if len(ids) > 1 else None

    @property
    def extra_state_attributes(self) -> dict:
        spk = self.speaker
        return {
            "host": spk.host,
            "serial_number": spk.serial,
            "room_placement": spk.room,
            "battery_level": spk.battery,
            "signal_strength": spk.signal,
            "sleep_timer": spk.timer,
            "group_role": spk.group_role,
            "group_link_id": spk.group_link_id,
        }

    # ------------------------------------------------------------------ commands
    def _require_available(self) -> None:
        if not self.speaker.available:
            raise HomeAssistantError(f"{self.speaker.display_name} is not reachable")

    async def async_turn_on(self) -> None:
        self._require_available()
        self.speaker.wake()

    async def async_turn_off(self) -> None:
        self._require_available()
        self.speaker.sleep()

    async def async_set_volume_level(self, volume: float) -> None:
        self._require_available()
        self.speaker.set_volume(round(volume * 100))
        self.async_write_ha_state()

    async def _play_control(self, action: str) -> None:
        self._require_available()
        self._media_source.play_control(action)

    async def async_media_play(self) -> None:
        await self._play_control("play")

    async def async_media_pause(self) -> None:
        await self._play_control("pause")

    async def async_media_stop(self) -> None:
        await self._play_control("stop")

    async def async_media_next_track(self) -> None:
        await self._play_control("next")

    async def async_media_previous_track(self) -> None:
        await self._play_control("prev")

    async def async_select_source(self, source: str) -> None:
        self._require_available()
        if not self._media_source.play_favorite(source):
            raise ServiceValidationError(f"Unknown favorite: {source}")

    async def async_save_favorite(self, slot: int) -> None:
        """Save the radio station playing now into favorite slot 1-5."""
        self._require_available()
        if not self._media_source.save_favorite(slot):
            raise ServiceValidationError(
                f"{self.speaker.display_name} isn't playing a radio station that can be saved as a favorite"
            )

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        self._require_available()
        if not self.speaker.set_voicing(sound_mode):
            raise ServiceValidationError(f"Unknown sound mode: {sound_mode}")

    # ------------------------------------------------------------------ grouping
    def _speaker_for(self, entity_id: str) -> LibratoneSpeaker:
        spk = next((s for s in self._hub.speakers if s.entity_id == entity_id), None)
        if spk is None:
            raise ServiceValidationError(f"{entity_id} is not a Libratone speaker")
        return spk

    async def async_join_players(self, group_members: list[str]) -> None:
        """Make this speaker the master and link the others to it (like the app does)."""
        self._require_available()
        master = self.speaker
        members = [self._speaker_for(e) for e in group_members if e != self.entity_id]
        link_id = master.group_link_id if master.group_role == "MASTER" else None
        if not link_id:
            # Same shape the app uses: <MasterName>_<MasterSerial>_<random>
            link_id = master.new_link_id()
            master.group_join(link_id)
        for member in members:
            member.group_join(link_id)

    async def async_unjoin_player(self) -> None:
        spk = self.speaker
        if not spk.group_link_id:
            return
        members = self._hub.group_members(spk)
        # A link needs two speakers: leaving a pair (or the master leaving) dissolves it
        targets = members if len(members) <= 2 or spk.group_role == "MASTER" else [spk]
        if spk not in targets:
            targets.append(spk)
        for member in targets:
            member.group_leave(spk.group_link_id)
