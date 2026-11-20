"""State + commands for one Libratone speaker. No Home Assistant imports."""
from __future__ import annotations

import json
import random
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from . import protocol as p
from .protocol import Cmd

if TYPE_CHECKING:
    from .hub import LibratoneHub

_LOGGER = logging.getLogger(__name__)

# A speaker is "available" while it answered within this many seconds.
AVAILABLE_TIMEOUT = 35.0

# Pretty names for player "play_type" values; anything else is title-cased.
SOURCE_NAMES = {
    "spotify": "Spotify",
    "airplay": "AirPlay",
    "bluetooth": "Bluetooth",
    "bt": "Bluetooth",
    "dlna": "DLNA",
    "aux": "Aux",
    "linein": "Aux",
    "vtuner": "Internet radio",
    "tunein": "TuneIn",
    "channel": "Favorite",
}


def _json(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


class LibratoneSpeaker:
    """One speaker. Identified by serial number; host may change at any time."""

    def __init__(
        self, hub: "LibratoneHub", host: str, serial: str | None = None,
        name: str | None = None, aliases: tuple[str, ...] = (),
    ) -> None:
        self.hub = hub
        self.host = host
        self.serial = serial
        self.expected_name = name   # used to re-identify legacy entries that have no serial yet
        # other names the speaker may answer with (entry title vs. stored device name)
        self.aliases = {n.casefold() for n in (name, *aliases) if n}
        self.name: str | None = None
        self.entity_id: str | None = None  # set by the HA layer, used for group member lists

        self.last_seen: float | None = None
        self.version: str | None = None
        self.power: str | None = None        # raw '0' / '1' / '2'
        self.play_status: str | None = None  # playing / paused / stopped / buffering
        self.volume: int | None = None
        self.voicing_id: str | None = None
        self.voicings: list[dict] = []
        self.room_id: str | None = None
        self.rooms: list[dict] = []
        self.player: dict = {}
        self.channels: list[dict] = []
        self.battery: int | None = None
        self.charging: str | None = None
        self.signal: str | None = None
        self.muted: bool | None = None
        self.timer: int | None = None
        self.group_role: str | None = None
        self.group_link_id: str | None = None
        self.channel: str | None = None      # stereo / left / right
        self.source_state: bytes = b""       # cmd 10, see protocol.MODE_*
        self.lssdp_playing: bool | None = None
        self.color: str | None = None        # e.g. 2002; part of the app's link ids

        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ listeners
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb) if cb in self._listeners else None

    def notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # pragma: no cover - never let a listener kill the hub
                _LOGGER.exception("Listener for %s failed", self)

    def __repr__(self) -> str:
        return f"<LibratoneSpeaker {self.name or self.expected_name} {self.serial} @ {self.host}>"

    # ------------------------------------------------------------------ state
    @property
    def available(self) -> bool:
        return self.last_seen is not None and time.monotonic() - self.last_seen < AVAILABLE_TIMEOUT

    @property
    def display_name(self) -> str:
        return self.name or self.expected_name or f"Libratone {self.host}"

    @property
    def bluetooth_playing(self) -> bool:
        return len(self.source_state) > 2 and self.source_state[2] == p.BT_PLAYING

    @property
    def effective_status(self) -> str | None:
        """play_status, corrected: cmd 51 reports Bluetooth playback as paused, LSSDP and cmd 10 know better."""
        if self.play_status == "playing":
            return "playing"
        if self.bluetooth_playing or self.lssdp_playing:
            return "playing"
        return self.play_status

    @property
    def is_sleeping(self) -> bool:
        return self.power == p.POWER_SLEEP

    @property
    def voicing(self) -> str | None:
        return self._id_to_name(self.voicing_id, self.voicings)

    @property
    def voicing_names(self) -> list[str]:
        return [v["name"] for v in self.voicings if "name" in v]

    @property
    def room(self) -> str | None:
        return self._id_to_name(self.room_id, self.rooms)

    @property
    def room_names(self) -> list[str]:
        return [r["name"] for r in self.rooms if "name" in r]

    @property
    def favorite_names(self) -> list[str]:
        return [self._channel_label(c) for c in sorted(self.channels, key=lambda c: c.get("channel_id", 0))]

    @staticmethod
    def _id_to_name(item_id: str | None, items: list[dict]) -> str | None:
        for item in items:
            if item.get("voicingId") == item_id:
                return item.get("name")
        return None

    @staticmethod
    def _channel_label(channel: dict) -> str:
        return f"{channel.get('channel_id')}: {channel.get('channel_name') or 'Favorite'}"

    # --- media info (Spotify fills artist/album; radio only title/subtitle)
    # Streaming sources (Spotify) send play_artist/play_album; then play_subtitle is the
    # track and play_title the playlist/context. Radio/favorites only send title/subtitle.
    @property
    def _has_track_info(self) -> bool:
        return "play_artist" in self.player

    @property
    def media_title(self) -> str | None:
        pl = self.player
        if self._has_track_info:
            return pl.get("play_subtitle") or pl.get("play_title") or None
        return pl.get("play_title") or None

    @property
    def media_artist(self) -> str | None:
        key = "play_artist" if self._has_track_info else "play_subtitle"
        return self.player.get(key) or None

    @property
    def media_album(self) -> str | None:
        return self.player.get("play_album") or None

    @property
    def media_playlist(self) -> str | None:
        return (self.player.get("play_title") or None) if self._has_track_info else None

    @property
    def media_image_url(self) -> str | None:
        uri = self.player.get("play_album_uri") or ""
        return uri if uri.startswith(("http://", "https://")) else None

    @property
    def media_content_id(self) -> str | None:
        return self.player.get("play_identity") or None

    @property
    def source(self) -> str | None:
        """Current favorite name if a favorite is playing, otherwise the source type."""
        if self.bluetooth_playing:
            return "Bluetooth"
        pl = self.player
        ident = str(pl.get("play_identity") or "")
        for ch in self.channels:
            if ident and ident in (str(ch.get("channel_identity")), str(ch.get("channel_id"))):
                return self._channel_label(ch)
        ptype = (pl.get("play_type") or "").lower()
        if not ptype or (ptype == "channel" and not ident):
            return None
        return SOURCE_NAMES.get(ptype, ptype.title())

    # ------------------------------------------------------------------ incoming
    def handle_frame(self, frame: p.Frame) -> bool:
        """Apply a frame to the state. Returns True if anything visible changed."""
        self.last_seen = time.monotonic()
        cmd, text = frame.cmd, frame.text
        if not frame.data:
            return False

        try:
            if cmd == Cmd.POWER_MODE:
                return self._set("power", text[:1])
            if cmd == Cmd.PLAY_STATUS:
                changed = self._set("play_status", p.PLAY_STATUS.get(text[:1], self.play_status))
                if changed:
                    self._recheck_lssdp()   # its playing flag would otherwise lag up to a poll interval
                return changed
            if cmd == Cmd.SOURCE_STATE:
                changed = self._set("source_state", bytes(frame.data))
                if changed:
                    self._recheck_lssdp()
                return changed
            if cmd == Cmd.SOURCE_MODE:
                self.request(Cmd.SOURCE_STATE, Cmd.PLAYER)   # mode switched: fetch the details now
                return False
            if cmd == Cmd.VOLUME:
                return self._set("volume", p.parse_int(text))
            if cmd == Cmd.PLAYER:
                data = _json(text)
                return self._set("player", data if isinstance(data, dict) else {})
            if cmd in (Cmd.VOICING, Cmd.VOICING_SET):
                return self._set("voicing_id", text)
            if cmd in (Cmd.ROOM, Cmd.ROOM_SET):
                return self._set("room_id", text)
            if cmd == Cmd.VOICING_LIST:
                data = _json(text)
                return isinstance(data, list) and self._set("voicings", data)
            if cmd == Cmd.ROOM_LIST:
                data = _json(text)
                return isinstance(data, list) and self._set("rooms", data)
            if cmd == Cmd.CHANNELS:
                data = _json(text)
                return isinstance(data, list) and self._set("channels", data)
            if cmd == Cmd.NAME:
                return self._set("name", text or self.name)
            if cmd == Cmd.CHANNEL:
                return self._set("channel", p.CHANNELS.get(text[:1], self.channel))
            if cmd == Cmd.COLOR:
                return self._set("color", text or self.color)
            if cmd == Cmd.SERIAL:
                return self._set("serial", text or self.serial)
            if cmd == Cmd.VERSION:
                return self._set("version", text)
            if cmd in (Cmd.BATTERY, Cmd.BATTERY_ALT):
                return self._set("battery", p.parse_int(text))
            if cmd == Cmd.CHARGING:
                return self._set("charging", text)
            if cmd == Cmd.SIGNAL:
                return self._set("signal", text)
            if cmd == Cmd.MUTE:
                return self._set("muted", text.upper() == "MUTE")
            if cmd == Cmd.TIMER:
                return self._set("timer", p.parse_timer(frame.data))
            if cmd == Cmd.GROUP:
                info = p.parse_group(text)
                if info is None:
                    _LOGGER.debug("%s: unknown group payload %r", self, text)
                    return False
                return self.apply_group(info)
        except Exception:  # never let a weird payload break the receive path
            _LOGGER.debug("%s: failed to parse cmd %s data %r", self, cmd, frame.data, exc_info=True)
        return False

    def _set(self, attr: str, value: Any) -> bool:
        if getattr(self, attr) == value:
            return False
        setattr(self, attr, value)
        return True

    # ------------------------------------------------------------------ outgoing
    def _send(self, cmd: int, data: str | None = None) -> None:
        self.hub.send(self.host, p.build(cmd, data))

    def request(self, *cmds: int) -> None:
        for cmd in cmds:
            self.hub.send(self.host, p.build_get(cmd))

    def refresh(self, full: bool = False) -> None:
        self.request(*(p.POLL_SLOW if full else ()), *p.POLL_FAST)
        # group state isn't readable with a GET; the LSSDP status reply carries it
        self.hub.send(self.host, p.LSSDP_MSEARCH, port=p.PORT_LSSDP)

    def apply_lssdp(self, fields: dict[str, str]) -> tuple[bool, bool]:
        """Apply an LSSDP status. Returns (group changed, anything else changed)."""
        group_changed = self.apply_group(p.group_from_lssdp(fields))
        channel = p.channel_from_lssdp(fields)
        other_changed = channel is not None and self._set("channel", channel)
        other_changed |= self._set("lssdp_playing", p.playing_from_lssdp(fields))
        return group_changed, other_changed

    def _recheck_lssdp(self) -> None:
        if self.host:
            self.hub.send(self.host, p.LSSDP_MSEARCH, port=p.PORT_LSSDP)

    def set_channel(self, channel: str) -> bool:
        """stereo / left / right"""
        code = p.CHANNEL_CODES.get(channel)
        if code is None:
            return False
        self._send(Cmd.CHANNEL, code)
        if self._set("channel", channel):  # optimistic; the notification / next LSSDP poll confirms
            self.notify()
        return True

    def new_link_id(self) -> str:
        """Same shape as the app: <Name>_<Serial>-<Color>_<random>"""
        serial = self.serial or "x"
        if self.color:
            serial = f"{serial}-{self.color}"
        return f"{self.name or self.display_name}_{serial}_{random.randint(10**9, 2**31 - 1)}"

    def apply_group(self, info: p.GroupInfo) -> bool:
        """Set group role/link id (from LSSDP or a 103 notification). Returns True if changed."""
        changed = self._set("group_role", info.role)
        changed |= self._set("group_link_id", info.link_id)
        return changed

    def _after_command(self, *extra: int) -> None:
        """Re-read state shortly after a command (plus any slow-polled value it changed)."""
        self.hub.schedule_refresh(self, extra)

    def play_control(self, action: str) -> None:
        self._send(Cmd.PLAY_CONTROL, p.PLAY_CONTROL[action])
        self._after_command()

    def set_volume(self, volume: int) -> None:
        volume = max(0, min(100, int(volume)))
        self._send(Cmd.VOLUME, str(volume))
        self.volume = volume
        self._after_command()

    def set_voicing(self, name: str) -> bool:
        return self._set_by_name(name, self.voicings, Cmd.VOICING_SET, "voicing_id", Cmd.VOICING)

    def set_room(self, name: str) -> bool:
        return self._set_by_name(name, self.rooms, Cmd.ROOM_SET, "room_id", Cmd.ROOM)

    def _set_by_name(self, name: str, items: list[dict], cmd: int, attr: str, get_cmd: int) -> bool:
        for item in items:
            if item.get("name") == name:
                self._send(cmd, item["voicingId"])
                if self._set(attr, item["voicingId"]):  # optimistic; the re-read confirms
                    self.notify()
                self._after_command(get_cmd)
                return True
        return False

    def play_favorite(self, favorite: str | int) -> bool:
        """Accepts a channel id (1..5) or a label as produced by favorite_names."""
        fid = str(favorite).split(":", 1)[0].strip()
        if fid not in {"1", "2", "3", "4", "5"}:
            for ch in self.channels:
                if favorite in (ch.get("channel_name"), self._channel_label(ch)):
                    fid = str(ch.get("channel_id"))
                    break
            else:
                return False
        payload = json.dumps(
            {"isFromChannel": False, "play_identity": fid, "play_subtitle": fid,
             "play_title": "channel", "play_type": "channel", "token": ""},
            separators=(",", ":"),
        )
        self._send(Cmd.PLAYER_SET, payload)
        self._after_command()
        return True

    def sleep(self) -> None:
        self._send(Cmd.TIMER, "20")
        self._after_command(Cmd.TIMER)

    def wake(self) -> None:
        self._send(Cmd.TIMER, "00")
        self._after_command(Cmd.TIMER)

    def set_sleep_timer(self, seconds: int) -> None:
        """Speaker goes to standby after `seconds` (verified: GET 15 then counts down)."""
        seconds = max(1, min(0xFFFF, int(seconds)))   # 0 would mean "sleep now"
        self._send(Cmd.TIMER, f"2{seconds}")
        if self._set("timer", seconds):
            self.notify()
        self._after_command(Cmd.TIMER)

    def cancel_sleep_timer(self) -> None:
        self._send(Cmd.TIMER, "F0")
        if self._set("timer", None):
            self.notify()
        self._after_command(Cmd.TIMER)

    def group_join(self, link_id: str) -> None:
        self._send(Cmd.GROUP_JOIN, f"LINK {link_id}")

    def group_leave(self, link_id: str) -> None:
        self._send(Cmd.GROUP_LEAVE, f"LINK {link_id}")
