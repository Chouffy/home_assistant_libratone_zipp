"""A fake Libratone speaker on a loopback address (127.0.0.x), speaking the real protocol.

Replies to GETs on 7777 by sending to <controller>:7778, and can push notifications
to <controller>:3333, mirroring what the real speakers do (see libratone-sniffing).
"""
from __future__ import annotations

import asyncio
import json
import socket

from custom_components.libratone_zipp import protocol as p
from custom_components.libratone_zipp.protocol import Cmd

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
            Cmd.CHARGING: "2", Cmd.SIGNAL: "-89,-34,5/5", Cmd.MUTE: "UNMUTE",
        }
        self.received: list[p.Frame] = []
        self.ip: str | None = None
        self.controller: str = "127.0.0.1"
        self._transport: asyncio.DatagramTransport | None = None
        self._lssdp: asyncio.DatagramTransport | None = None
        self.name = name
        # group state as reported via LSSDP: "F" free, "M" master, "S" slave
        self.lssdp_state = "F"
        self.zone = ""
        self.lssdp_queries = 0

    async def start(self, ip: str) -> "FakeSpeaker":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, p.PORT_CONTROL))
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(lambda: _Proto(self), sock=sock)
        lsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lsock.bind((ip, p.PORT_LSSDP))
        self._lssdp, _ = await loop.create_datagram_endpoint(lambda: _LssdpProto(self), sock=lsock)
        self.ip = ip
        return self

    def stop(self) -> None:
        for t in (self._transport, self._lssdp):
            if t:
                t.close()
        self._transport = self._lssdp = None

    def set_group(self, state: str, link_id: str = "") -> None:
        """What LSSDP reports: state F/M/S, link id without the 'LINK ' prefix."""
        self.lssdp_state = state
        self.zone = f"LINK {link_id}" if link_id else ""

    def _on_msearch(self, data: bytes, src: str) -> None:
        if not data.startswith(b"M-SEARCH") or not self._lssdp:
            return
        self.lssdp_queries += 1
        reply = (
            "HTTP/1.1 200 OK\r\nHOST: 239.255.255.250:1800\r\nPROTOCOL: Version 1.0\r\n"
            f"DeviceName: {self.name}_{self.serial}\r\nDeviceID: c467b5000000\r\n"
            f"DeviceState: {self.lssdp_state},S,N\r\nPORT: 7777\r\nZoneID: {self.zone}\r\n"
            f"Creator: \r\nIPAddr: {self.ip}\r\nStereoPairID: \r\n"
        )
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
