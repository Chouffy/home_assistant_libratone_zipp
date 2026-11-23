"""A fake Libratone speaker on a loopback address (127.0.0.x), speaking the real protocol.

Replies to GETs on 7777 by sending to <controller>:7778, and can push notifications
to <controller>:3333, mirroring what the real speakers do (values from packet captures).
"""
from __future__ import annotations

import asyncio
import json
import socket

from python_libratone_zipp import protocol as p
from python_libratone_zipp.protocol import Cmd

SPOTIFY_PLAYER = {
    "isFromChannel": False,
    "play_album": "Appetite For Destruction",
    "play_album_uri": "https://i.scdn.co/image/ab67616d0000b27321ebf49b3292c3f0f575f0f5",
    "play_artist": "Guns N' Roses",
    "play_identity": "spotify:playlist:37i9dQZF1E8PIzyPX3HgQg",
    "play_preset_available": 1,
    "play_subtitle": "Sweet Child O' Mine",
    "play_title": "Don't Stop Believin' Radio",
    "play_token": "",
    "play_type": "spotify",
}
EMPTY_PLAYER = {"isFromChannel": False, "play_identity": "", "play_subtitle": "", "play_title": "",
                "play_token": "", "play_type": "channel"}
VOICINGS = [{"name": "Neutral", "voicingId": "V100"}, {"name": "Rock the house", "voicingId": "V103"}]
ROOMS = [{"name": "Neutral", "voicingId": "neutral"}, {"name": "Shelf", "voicingId": "shelf"}]
CHANNELS = [{"channel_id": i, "channel_identity": str(1000 + i), "channel_name": n, "channel_type": "vtuner"}
            for i, n in enumerate(["BBC Radio 6 Music", "BBC Radio 4", "Radio Paradise", "Bossa Jazz", "Chinese Music"], 1)]


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, fake: "FakeSpeaker") -> None:
        self.fake = fake

    def datagram_received(self, data, addr) -> None:
        self.fake._on_packet(data, addr[0])


# loopback addresses of running fakes; the hub's LSSDP search goes only here in tests (never a real broadcast)
SEARCH_TARGETS: list[str] = []
NOTIFY_INTERVAL = 0.5   # real speakers: ~10 s


class _LssdpProto(asyncio.DatagramProtocol):
    def __init__(self, fake: "FakeSpeaker") -> None:
        self.fake = fake

    def datagram_received(self, data, addr) -> None:
        self.fake._on_msearch(data, addr[0])


class FakeSpeaker:
    def __init__(self, serial: str, name: str, player: dict | None = None, volume: int = 16) -> None:
        self.serial = serial
        self.values: dict[int, str] = {
            Cmd.SERIAL: serial, Cmd.NAME: name, Cmd.VERSION: "879", Cmd.POWER_MODE: "0",
            Cmd.PLAY_STATUS: "0", Cmd.VOLUME: str(volume), Cmd.VOICING: "V103", Cmd.ROOM: "shelf",
            Cmd.PLAYER: json.dumps(player or EMPTY_PLAYER), Cmd.VOICING_LIST: json.dumps(VOICINGS),
            Cmd.ROOM_LIST: json.dumps(ROOMS), Cmd.CHANNELS: json.dumps(CHANNELS), Cmd.BATTERY: "100",
            Cmd.CHARGING: "2", Cmd.SIGNAL: "-89,-34,5/5", Cmd.MUTE: "UNMUTE", Cmd.COLOR: "2002",
            Cmd.SOURCE_STATE: bytes.fromhex("340c00f3040000"),
            Cmd.TIMER: b"\xff" * 5,
            Cmd.SSID: '"Your-WiFi-SSID"',
            Cmd.PRIVATE_MODE: "0",                      # touch-panel mute
        }
        self.received: list[p.Frame] = []
        self.ip: str | None = None
        self.controller: str = "127.0.0.1"
        self._transport: asyncio.DatagramTransport | None = None
        self._lssdp: asyncio.DatagramTransport | None = None
        self.name = name
        # group state as reported via LSSDP: "F" free, "M" master, "S" slave
        self.lssdp_state = "F"
        self.channel = "S"           # LSSDP letter: S stereo / L left / R right
        self.zone = ""
        self.lssdp_queries = 0
        self.lssdp_enabled = True       # False: silent on LSSDP (like a network that drops broadcasts)
        self.mac = "c467b50000" + serial[-2:]   # vendor prefix + fake device part
        self._notify_task: asyncio.Task | None = None

    async def start(self, ip: str) -> "FakeSpeaker":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, p.PORT_CONTROL))
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(lambda: _Proto(self), sock=sock)
        lsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # the hub listens on 0.0.0.0:1800
        lsock.bind((ip, p.PORT_LSSDP))
        self._lssdp, _ = await loop.create_datagram_endpoint(lambda: _LssdpProto(self), sock=lsock)
        self.ip = ip
        SEARCH_TARGETS.append(ip)
        self._notify_task = loop.create_task(self._announce())
        return self

    def _lssdp_text(self, first_line: str) -> str:
        return (
            f"{first_line}\r\nHOST: 239.255.255.250:1800\r\nPROTOCOL: Version 1.0\r\n"
            f"DeviceName: {self.name}_{self.serial}\r\nDeviceID: {self.mac}\r\n"
            f"DeviceState: {self.lssdp_state},{self.channel},{self._playing_letter()}\r\nPORT: 7777\r\n"
            f"ZoneID: {self.zone}\r\nCreator: \r\nIPAddr: {self.ip}\r\nStereoPairID: \r\n"
        )

    async def _announce(self) -> None:
        """Like the real speakers' periodic LSSDP broadcast (to the hub's 0.0.0.0:1800 on loopback)."""
        while True:
            await asyncio.sleep(NOTIFY_INTERVAL)
            if self._lssdp and self.lssdp_enabled:
                text = self._lssdp_text("NOTIFY * HTTP/1.1").replace("PROTOCOL", "NTS: ssdp-alive\r\nPROTOCOL", 1)
                self._lssdp.sendto(text.encode(), ("127.0.0.1", p.PORT_LSSDP))

    def stop(self) -> None:
        if self._notify_task:
            self._notify_task.cancel()
            self._notify_task = None
        if self.ip in SEARCH_TARGETS:
            SEARCH_TARGETS.remove(self.ip)
        for t in (self._transport, self._lssdp):
            if t:
                t.close()
        self._transport = self._lssdp = None

    def _playing_letter(self) -> str:
        """Like the real speakers: P while audio plays, including Bluetooth (where cmd 51 says paused)."""
        src = self.values[Cmd.SOURCE_STATE]
        return "P" if self.values[Cmd.PLAY_STATUS] == "0" or (len(src) > 2 and src[2] == 0x08) else "N"

    def set_group(self, state: str, link_id: str = "") -> None:
        """What LSSDP reports: state F/M/S, link id without the 'LINK ' prefix."""
        self.lssdp_state = state
        self.zone = f"LINK {link_id}" if link_id else ""

    def _on_msearch(self, data: bytes, src: str) -> None:
        if not data.startswith(b"M-SEARCH") or not self._lssdp or not self.lssdp_enabled:
            return
        self.lssdp_queries += 1
        reply = self._lssdp_text("HTTP/1.1 200 OK")
        # like the real speakers: reply goes to the searcher's port 7778, from another socket
        self._lssdp.sendto(reply.encode(), (src, p.PORT_RESULT))

    async def move(self, ip: str) -> None:
        """Simulate DHCP handing out a new address."""
        self.stop()
        await self.start(ip)

    def _on_packet(self, data: bytes, src: str) -> None:
        frame = p.parse(data)
        if frame is None:
            return
        self.controller = src
        self.received.append(frame)
        if frame.ctype == p.TYPE_SET:
            if frame.cmd == Cmd.VOLUME:
                self.values[Cmd.VOLUME] = frame.text
            elif frame.cmd == Cmd.VOICING_SET:
                self.values[Cmd.VOICING] = frame.text
            elif frame.cmd == Cmd.ROOM_SET:
                self.values[Cmd.ROOM] = frame.text
            elif frame.cmd == Cmd.TIMER and frame.text == "20":
                self.values[Cmd.POWER_MODE] = "2"
            elif frame.cmd == Cmd.TIMER and frame.text == "00":
                self.values[Cmd.POWER_MODE] = "0"
            elif frame.cmd == Cmd.COLOR_SET:
                self.values[Cmd.COLOR] = frame.text
                self._send(frame.cmd, "", p.PORT_RESULT)
                self.notify(Cmd.COLOR_SET, frame.text)
                return
            elif frame.cmd == Cmd.NAME:
                self.values[Cmd.NAME] = frame.text
                self.name = frame.text
                self._send(frame.cmd, "", p.PORT_RESULT)
                self.notify(Cmd.NAME, frame.text)
                return
            elif frame.cmd == Cmd.CHANNEL_SAVE:
                entry = json.loads(frame.text)
                channels = [c for c in json.loads(self.values[Cmd.CHANNELS]) if c["channel_id"] != entry["channel_id"]]
                channels.append(entry)
                self.values[Cmd.CHANNELS] = json.dumps(sorted(channels, key=lambda c: c["channel_id"]))
            elif frame.cmd == Cmd.TIMER and frame.text == "F0":
                self.values[Cmd.TIMER] = b"\xff" * 5
            elif frame.cmd == Cmd.TIMER and frame.text.startswith("2"):
                # real format (verified on a Zipp): '2' + remaining seconds uint16 little-endian + 2 zero bytes
                self.values[Cmd.TIMER] = b"2" + int(frame.text[1:]).to_bytes(2, "little") + b"\x00\x00"
            elif frame.cmd == Cmd.CHANNEL:
                self.channel = {"0": "S", "1": "L", "2": "R"}[frame.text]
                self._send(frame.cmd, "", p.PORT_RESULT)
                self.notify(Cmd.CHANNEL, frame.text)      # the real speaker echoes it as a notification
                return
            elif frame.cmd == Cmd.PLAY_CONTROL and frame.text == "PAUSE":
                self.values[Cmd.PLAY_STATUS] = "2"
            self._send(frame.cmd, "", p.PORT_RESULT)  # empty ack like the real thing
            return
        self._send(frame.cmd, self.values.get(frame.cmd, ""), p.PORT_RESULT)

    def _send(self, cmd: int, text: str, port: int) -> None:
        if self._transport:
            self._transport.sendto(p.build(cmd, text, ctype=p.TYPE_GET), (self.controller, port))

    def notify(self, cmd: int, text: str) -> None:
        """Push an asynchronous notification (to port 3333)."""
        self._send(cmd, text, p.PORT_NOTIFY)

    def sets(self, cmd: int) -> list[str]:
        return [f.text for f in self.received if f.ctype == p.TYPE_SET and f.cmd == cmd]
