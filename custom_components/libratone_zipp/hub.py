"""Shared asyncio UDP hub for all Libratone speakers.

The speakers always answer to fixed ports on the controller (7778 for replies, 3333 for
notifications), so only one process/socket pair can talk to them. The hub owns those
sockets, routes packets to speakers by source IP, and keeps the IP -> speaker mapping
correct when DHCP hands a speaker a new address: speakers are identified by serial number,
and an unknown IP that reports a known serial takes over that speaker.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from . import protocol as p
from .protocol import Cmd
from .speaker import LibratoneSpeaker

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = 10          # seconds between fast polls
SLOW_POLL_EVERY = 30        # every Nth poll also asks the slow values (~5 min)
SCAN_INTERVAL = 60          # min seconds between subnet scans while a speaker is missing
SCAN_INTERVAL_LONG = 300    # ... once it has been missing for SCAN_BACKOFF_AFTER seconds
SCAN_BACKOFF_AFTER = 600


class _Endpoint(asyncio.DatagramProtocol):
    def __init__(self, hub: "LibratoneHub", port: int) -> None:
        self.hub = hub
        self.port = port

    def datagram_received(self, data: bytes, addr) -> None:
        self.hub._on_datagram(data, addr[0], self.port)

    def error_received(self, exc: Exception) -> None:
        # ICMP port/host unreachable for a sent packet; harmless, the speaker is just gone
        _LOGGER.debug("UDP error on port %s: %s", self.port, exc)


def _bound_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", port))
    sock.setblocking(False)
    return sock


class LibratoneHub:
    def __init__(self) -> None:
        self.speakers: list[LibratoneSpeaker] = []
        # ip -> {"serial":..., "name":..., "ts":...} for every Libratone that answered us
        self.seen: dict[str, dict] = {}
        self._result: asyncio.DatagramTransport | None = None
        self._notify: asyncio.DatagramTransport | None = None
        self._task: asyncio.Task | None = None
        self._probes: dict[str, list[asyncio.Future]] = {}
        self._last_scan = 0.0
        self._missing_since: float | None = None
        self._availability: dict[int, bool] = {}
        self._timers: set[asyncio.TimerHandle] = set()

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._result, _ = await loop.create_datagram_endpoint(
            lambda: _Endpoint(self, p.PORT_RESULT), sock=_bound_socket(p.PORT_RESULT))
        self._notify, _ = await loop.create_datagram_endpoint(
            lambda: _Endpoint(self, p.PORT_NOTIFY), sock=_bound_socket(p.PORT_NOTIFY))
        self._task = loop.create_task(self._poll_loop(), name="libratone_hub_poll")
        _LOGGER.debug("Libratone hub listening on %s and %s", p.PORT_RESULT, p.PORT_NOTIFY)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for t in (self._result, self._notify):
            if t:
                t.close()
        for handle in self._timers:
            handle.cancel()
        self._timers.clear()
        self._result = self._notify = self._task = None

    # ------------------------------------------------------------------ registry
    def add_speaker(self, host: str, serial: str | None, name: str | None) -> LibratoneSpeaker:
        spk = LibratoneSpeaker(self, host, serial=serial, name=name)
        self.speakers.append(spk)
        spk.refresh(full=True)
        return spk

    def remove_speaker(self, spk: LibratoneSpeaker) -> None:
        if spk in self.speakers:
            self.speakers.remove(spk)
        self._availability.pop(id(spk), None)

    def by_host(self, host: str) -> LibratoneSpeaker | None:
        return next((s for s in self.speakers if s.host == host), None)

    def by_serial(self, serial: str) -> LibratoneSpeaker | None:
        return next((s for s in self.speakers if s.serial == serial), None)

    def group_members(self, spk: LibratoneSpeaker) -> list[LibratoneSpeaker]:
        """All speakers sharing spk's link id, master first. Empty if not grouped."""
        if not spk.group_link_id:
            return []
        members = [s for s in self.speakers if s.group_link_id == spk.group_link_id]
        return sorted(members, key=lambda s: not self._is_master(s))

    def group_master(self, spk: LibratoneSpeaker) -> LibratoneSpeaker | None:
        return next((s for s in self.group_members(spk) if self._is_master(s)), None)

    @staticmethod
    def _is_master(spk: LibratoneSpeaker) -> bool:
        """MASTER if the speaker says so; with only GROUPED known, infer it from the
        link id, which the app builds as <MasterName>_<MasterSerial>_<random>."""
        if spk.group_role in ("MASTER", "SLAVE"):
            return spk.group_role == "MASTER"
        link = spk.group_link_id or ""
        if spk.serial and f"_{spk.serial}_" in link:
            return True
        name = spk.name or spk.expected_name
        return bool(name) and link.startswith(f"{name}_")

    # ------------------------------------------------------------------ sending
    def send(self, host: str, packet: bytes, port: int = p.PORT_CONTROL) -> None:
        if not self._result or not host:
            return
        try:
            self._result.sendto(packet, (host, port))
        except OSError as err:
            _LOGGER.debug("Send to %s failed: %s", host, err)

    def schedule_refresh(self, spk: LibratoneSpeaker, extra: tuple[int, ...] = ()) -> None:
        """Refresh shortly after a command so the UI follows quickly."""
        def _refresh() -> None:
            spk.request(*extra)
            spk.refresh()

        for delay in (0.4, 1.5):
            self._call_later(delay, _refresh)

    def _call_later(self, delay: float, func) -> None:
        holder: list[asyncio.TimerHandle] = []

        def _run() -> None:
            self._timers.discard(holder[0])
            func()

        holder.append(asyncio.get_running_loop().call_later(delay, _run))
        self._timers.add(holder[0])

    # ------------------------------------------------------------------ receiving
    def _on_datagram(self, data: bytes, ip: str, port: int) -> None:
        frame = p.parse(data)
        if frame is None:
            return
        if port == p.PORT_NOTIFY and self._notify:
            try:
                self._notify.sendto(p.build_ack(frame), (ip, p.PORT_NOTIFY_ACK))
            except OSError:
                pass

        self._remember(ip, frame)
        spk = self.by_host(ip)

        # The IP we route on now reports a different serial -> it's another device
        if spk and frame.cmd == Cmd.SERIAL and spk.serial and frame.text and frame.text != spk.serial:
            _LOGGER.info("%s no longer at %s (found serial %s there)", spk, ip, frame.text)
            spk.host = ""
            spk = None

        if spk is None:
            spk = self._claim(ip)
            if spk is None:
                return

        changed = spk.handle_frame(frame)
        if frame.cmd == Cmd.GROUP:
            # group membership affects every speaker's group_members
            for s in self.speakers:
                s.notify()
            return
        if changed or not self._availability.get(id(spk)):
            self._availability[id(spk)] = True
            spk.notify()
            if spk.group_link_id and self._is_master(spk) and frame.cmd in (Cmd.PLAYER, Cmd.PLAY_STATUS):
                for member in self.group_members(spk):
                    if member is not spk:
                        member.notify()

    def _remember(self, ip: str, frame: p.Frame) -> None:
        info = self.seen.setdefault(ip, {})
        info["ts"] = time.monotonic()
        if frame.cmd == Cmd.SERIAL and frame.text:
            info["serial"] = frame.text
        elif frame.cmd == Cmd.NAME and frame.text:
            info["name"] = frame.text
        if "serial" in info and "name" in info:
            for fut in self._probes.pop(ip, []):
                if not fut.done():
                    fut.set_result(dict(info))

    def _claim(self, ip: str) -> LibratoneSpeaker | None:
        """An unknown IP answered. Re-home a known speaker to it if the identity matches."""
        info = self.seen.get(ip, {})
        serial, name = info.get("serial"), info.get("name")
        spk = None
        if serial:
            spk = self.by_serial(serial)
        if spk is None and name:
            # legacy entry without serial: match by name, only if that speaker is missing
            matches = [s for s in self.speakers
                       if s.serial is None and not s.available
                       and (s.expected_name or "").casefold() == name.casefold()]
            if len(matches) == 1 and (serial is None or not self.by_serial(serial)):
                spk = matches[0]
                if serial:
                    spk.serial = serial
                elif "serial" not in info:
                    # ask for the serial first; we'll claim once it arrives
                    self.send(ip, p.build_get(Cmd.SERIAL))
                    return None
        if spk is None:
            if "serial" not in info and "name" not in info:
                # first contact from an unknown Libratone; ask who it is
                self.send(ip, p.build_get(Cmd.SERIAL))
                self.send(ip, p.build_get(Cmd.NAME))
            return None

        old = spk.host
        spk.host = ip
        _LOGGER.warning("Libratone %s moved from %s to %s", spk.display_name, old or "?", ip)
        spk.refresh(full=True)
        return spk

    # ------------------------------------------------------------------ probing / scanning
    async def probe(self, host: str, timeout: float = 3.0) -> dict | None:
        """Ask a host for serial+name. Returns {'serial','name'} or None."""
        fut = asyncio.get_running_loop().create_future()
        self._probes.setdefault(host, []).append(fut)
        for cmd in (Cmd.SERIAL, Cmd.NAME):
            self.send(host, p.build_get(cmd))
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            futs = self._probes.get(host)
            if futs and fut in futs:
                futs.remove(fut)

    def _scan_networks(self) -> set[ipaddress.IPv4Network]:
        nets: set[ipaddress.IPv4Network] = set()
        for host in [s.host for s in self.speakers] + list(self.seen):
            try:
                nets.add(ipaddress.ip_network(f"{host}/24", strict=False))
            except ValueError:
                continue
        return nets

    async def scan(self) -> None:
        """Ask every address in the speakers' /24s who they are (2 tiny UDP packets each)."""
        self._last_scan = time.monotonic()
        nets = self._scan_networks()
        _LOGGER.debug("Scanning %s for Libratone speakers", ", ".join(map(str, nets)) or "nothing")
        for net in nets:
            self.send(str(net.broadcast_address), p.build_get(Cmd.SERIAL))
            for i, addr in enumerate(net.hosts()):
                self.send(str(addr), p.build_get(Cmd.SERIAL))
                self.send(str(addr), p.build_get(Cmd.NAME))
                if i % 16 == 15:
                    await asyncio.sleep(0.05)

    # ------------------------------------------------------------------ poll loop
    async def _poll_loop(self) -> None:
        tick = 0
        while True:
            try:
                for spk in list(self.speakers):
                    full = tick % SLOW_POLL_EVERY == 0 or spk.serial is None or not spk.voicings
                    spk.refresh(full=full)
                await asyncio.sleep(POLL_INTERVAL)
                tick += 1
                self._check_availability()
                await self._maybe_scan()
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - keep polling no matter what
                _LOGGER.exception("Libratone poll loop error")
                await asyncio.sleep(POLL_INTERVAL)

    def _check_availability(self) -> None:
        for spk in self.speakers:
            avail = spk.available
            if self._availability.get(id(spk)) != avail:
                self._availability[id(spk)] = avail
                _LOGGER.info("%s is now %s", spk, "available" if avail else "unavailable")
                spk.notify()

    async def _maybe_scan(self) -> None:
        missing = [s for s in self.speakers if not s.available]
        now = time.monotonic()
        if not missing:
            self._missing_since = None
            return
        if self._missing_since is None:
            self._missing_since = now
            return  # give it one poll interval before scanning
        interval = SCAN_INTERVAL if now - self._missing_since < SCAN_BACKOFF_AFTER else SCAN_INTERVAL_LONG
        if now - self._last_scan >= interval:
            await self.scan()
