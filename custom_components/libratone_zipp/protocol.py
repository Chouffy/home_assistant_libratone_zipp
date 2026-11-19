"""Libratone (Libre Wireless LUCI-style) UDP protocol: frames, commands, value maps.

Pure Python, no Home Assistant imports, so it can be tested and reused standalone.

Frame layout (big endian), from the decompiled Android app (com.libratone.luci.LUCIPacket)
and confirmed with packet captures:

    aaaa  tt  cccc  ss  rrrr  llll  data...
    |     |   |     |   |     |
    |     |   |     |   |     +-- data length
    |     |   |     |   +-------- random request id (echoed in replies)
    |     |   |     +------------ status
    |     |   +------------------ command id
    |     +---------------------- type: 1 = get / notification, 2 = set
    +---------------------------- remote id, hardcoded by the app

Ports:
    7777/udp  speaker: commands are sent here
    7778/udp  controller: replies to commands arrive here (regardless of source port)
    3333/udp  controller: asynchronous notifications from the speaker
    3334/udp  speaker: acknowledgements of notifications
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import random
import struct

PORT_CONTROL = 7777
PORT_RESULT = 7778
PORT_NOTIFY = 3333
PORT_NOTIFY_ACK = 3334

REMOTE_ID = b"\xaa\xaa"
HEADER_LEN = 10

TYPE_GET = 1
TYPE_SET = 2


class Cmd(IntEnum):
    """Known command ids (names from com.libratone.model.LSSDPNode where known)."""

    VERSION = 5
    SOURCE_STATE = 10       # 7 opaque bytes, sent by the app on every refresh; meaning TBD
    POWER_MODE = 14         # '0' awake, '1' transitional, '2' sleeping
    TIMER = 15              # sleep timer; also used for sleep ("20") / wake ("00")
    PLAY_CONTROL = 40       # PLAY / PAUSE / STOP / NEXT / PREV
    PLAY_STATUS = 51        # '0' playing, '1' stopped, '2' paused, '3'..'5' transitional
    VOLUME = 64             # 0..100 as ASCII
    NAME = 90
    GROUP = 103             # notification only: FREE | GROUPED,LINK x | MASTER,LINK x | SLAVE,LINK x
    BATTERY = 256
    BATTERY_ALT = 257
    CHANNELS = 275          # JSON list of the 5 favorites
    PLAYER_SET = 277        # JSON, used to start a favorite
    PLAYER = 278            # JSON with title/artist/album/cover/source
    GROUP_JOIN = 502        # "LINK <link_id>"
    GROUP_LEAVE = 503       # "LINK <link_id>"
    VOICING = 516           # current voicing id, e.g. V103
    ROOM = 517              # current room placement id, e.g. shelf
    VOICING_SET = 518
    ROOM_SET = 519
    MUTE = 520              # MUTE / UNMUTE
    VOICING_LIST = 524      # JSON list
    ROOM_LIST = 525         # JSON list
    SIGNAL = 529            # "-89,-34,5/5"
    SERIAL = 769
    COLOR = 770
    CHARGING = 1284


PLAY_CONTROL = {"play": "PLAY", "pause": "PAUSE", "stop": "STOP", "next": "NEXT", "prev": "PREV"}

PLAY_STATUS = {
    "0": "playing",
    "1": "stopped",
    "2": "paused",
    "3": "buffering",
    "4": "buffering",
    "5": "buffering",
}

POWER_SLEEP = "2"

# Commands polled frequently (cheap, change often)
POLL_FAST: tuple[Cmd, ...] = (
    Cmd.POWER_MODE,
    Cmd.PLAY_STATUS,
    Cmd.VOLUME,
    Cmd.PLAYER,
    Cmd.VOICING,
)

# Commands polled rarely (identity, lists, slow-changing values)
POLL_SLOW: tuple[Cmd, ...] = (
    Cmd.SERIAL,
    Cmd.NAME,
    Cmd.VERSION,
    Cmd.VOICING_LIST,
    Cmd.ROOM_LIST,
    Cmd.ROOM,
    Cmd.CHANNELS,
    Cmd.BATTERY,
    Cmd.CHARGING,
    Cmd.SIGNAL,
    Cmd.MUTE,
    Cmd.TIMER,
)


@dataclass(slots=True)
class Frame:
    ctype: int
    cmd: int
    status: int
    request_id: int
    data: bytes

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace").strip("\x00").strip()


def build(cmd: int, data: str | bytes | None = None, ctype: int = TYPE_SET) -> bytes:
    """Build a frame ready to send."""
    if data is None:
        payload = b""
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = str(data).encode("utf-8")
    return (
        REMOTE_ID
        + struct.pack(">BHBHH", ctype, int(cmd), 0, random.randint(1, 0xFFFF), len(payload))
        + payload
    )


def build_get(cmd: int) -> bytes:
    return build(cmd, ctype=TYPE_GET)


def build_ack(frame: Frame) -> bytes:
    """Acknowledgement for a notification, as the app sends it (echoes the command)."""
    return REMOTE_ID + struct.pack(">BHBHH", TYPE_SET, frame.cmd, 0, random.randint(1, 0xFFFF), 0)


def parse(packet: bytes) -> Frame | None:
    """Parse a received frame; returns None for anything that isn't one."""
    if len(packet) < HEADER_LEN or packet[:2] != REMOTE_ID:
        return None
    ctype, cmd, status, request_id, length = struct.unpack(">BHBHH", packet[2:HEADER_LEN])
    data = bytes(packet[HEADER_LEN:HEADER_LEN + length]) if length else bytes(packet[HEADER_LEN:])
    return Frame(ctype=ctype, cmd=cmd, status=status, request_id=request_id, data=data)


@dataclass(slots=True)
class GroupInfo:
    role: str | None        # MASTER | SLAVE | GROUPED | None (free)
    link_id: str | None


def parse_group(text: str) -> GroupInfo | None:
    """Parse a cmd 103 notification. Returns None if the payload isn't understood."""
    s = text.strip().lstrip(":= ")
    if not s:
        return None
    upper = s.upper()
    if upper in ("FREE", "UNGROUPED") or upper.startswith(("UNGROUP", "UNLINK")):
        return GroupInfo(role=None, link_id=None)
    role, sep, rest = s.partition(",")
    if sep and role.upper() in ("MASTER", "SLAVE", "GROUPED") and rest.upper().startswith("LINK "):
        link_id = rest[5:].strip()
        return GroupInfo(role=role.upper(), link_id=link_id or None)
    return None


def parse_timer(data: bytes) -> int | None:
    """Defined sleep timer in seconds, or None if no timer is set."""
    if len(data) >= 3 and data[0] == ord("2"):
        return data[1] + data[2] * 256
    return None


def parse_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None
