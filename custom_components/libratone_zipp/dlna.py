"""Play media through the speaker's own UPnP/DLNA renderer (AVTransport).

Every Libratone speaker also runs a DLNA media renderer (UPnP description on :49152). Using it from this
integration means one media player entity can both control the speaker (Libratone protocol) and play
URLs / media-source items / TTS (DLNA), instead of two separate entities (this + the DLNA integration).
Verified 2026-11-21 on a Zipp: MP3 stream plays; the Libratone side then reports mode 0x32 (DLNA).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError
from async_upnp_client.profiles.dlna import DmrDevice

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .stream_proxy import async_proxy_url

if TYPE_CHECKING:
    from python_libratone_zipp import LibratoneSpeaker

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_PORTS = (49152, 49153, 49154)
DESCRIPTION_PATH = "/description.xml"

# HA media types -> UPnP classes (subset of what the DLNA integration maps)
UPNP_CLASS = {
    "music": "object.item.audioItem.musicTrack",
    "audio/mpeg": "object.item.audioItem.musicTrack",
    "radio": "object.item.audioItem.audioBroadcast",
    "channel": "object.item.audioItem.audioBroadcast",
    "podcast": "object.item.audioItem.audioBook",
}


class LibratoneDlna:
    def __init__(self, hass: HomeAssistant, speaker: "LibratoneSpeaker") -> None:
        self.hass = hass
        self.speaker = speaker
        self._device: DmrDevice | None = None
        self._host: str | None = None
        self._factory = UpnpFactory(
            AiohttpSessionRequester(async_get_clientsession(hass), with_sleep=True), non_strict=True
        )

    async def _get_device(self) -> DmrDevice:
        host = self.speaker.host
        if not host:
            raise HomeAssistantError(f"{self.speaker.display_name} has no known address")
        if self._device is not None and self._host == host:
            return self._device
        last_err: Exception | None = None
        for port in DESCRIPTION_PORTS:   # the renderer is usually on 49152; be lenient
            try:
                upnp = await self._factory.async_create_device(f"http://{host}:{port}{DESCRIPTION_PATH}")
            except (UpnpError, OSError, TimeoutError) as err:
                last_err = err
                continue
            if "AVTransport" not in " ".join(upnp.services):
                continue
            self._device, self._host = DmrDevice(upnp, None), host
            return self._device
        raise HomeAssistantError(f"No DLNA renderer found on {self.speaker.display_name}: {last_err}")

    async def async_model(self) -> str | None:
        """'LTH300' from the UPnP description (modelName + modelNumber)."""
        try:
            upnp = (await self._get_device()).device
        except HomeAssistantError:
            return None
        return f"{upnp.model_name or ''}{upnp.model_number or ''}".strip() or None

    async def sink_content_types(self) -> set[str] | None:
        """Content types the renderer accepts (e.g. audio/mpeg), or None if unknown."""
        try:
            dev = await self._get_device()
            await dev.async_update(do_ping=False)
        except (HomeAssistantError, UpnpError, OSError, TimeoutError):
            return None
        types = set()
        for info in dev.sink_protocol_info or []:
            protocol, _, fmt, _ = (info.split(":", 3) + ["", "", "", ""])[:4]
            if protocol.startswith("http"):
                types.add(fmt.lower().replace("/x-", "/", 1).partition(";")[0])
        return types or None

    async def _resolve_stream_url(self, url: str) -> tuple[str, str | None]:
        """The renderer doesn't follow HTTP redirects or read playlists (UPnP error 716 'resource not found').
        Follow redirects here and take the first stream from an .m3u/.pls playlist."""
        if not url.startswith(("http://", "https://")):
            return url, None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                final = str(resp.url)
                ctype = resp.headers.get("Content-Type", "").lower()
                is_playlist = any(t in ctype for t in ("mpegurl", "scpls", "x-pls")) or \
                    final.lower().split("?")[0].endswith((".m3u", ".m3u8", ".pls"))
                if is_playlist and "m3u8" not in final.lower():
                    text = (await resp.content.read(16384)).decode("utf-8", errors="replace")
                    for line in text.splitlines():
                        line = line.strip()
                        if line.lower().startswith("file") and "=" in line:   # .pls: File1=http://...
                            line = line.split("=", 1)[1].strip()
                        if line.startswith(("http://", "https://")):
                            _LOGGER.debug("%s: playlist %s -> %s", self.speaker.display_name, final, line)
                            return await self._resolve_stream_url(line)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("%s: could not pre-resolve %s: %s", self.speaker.display_name, url, err)
            return url, None
        if final != url:
            _LOGGER.debug("%s: %s redirects to %s", self.speaker.display_name, url, final)
        return final, (ctype.split(";")[0].strip() or None)

    async def async_play(self, url: str, title: str, media_type: str | None,
                         metadata: dict[str, Any] | None = None) -> None:
        url, content_type = await self._resolve_stream_url(url)
        if url.startswith("https://"):
            # the speaker's firmware can't open current https servers: relay through Home Assistant
            url = async_proxy_url(self.hass, url)
        try:
            dev = await self._get_device()
            await dev.async_update(do_ping=False)
            didl = await dev.construct_play_media_metadata(
                media_url=url,
                media_title=title,
                override_upnp_class=UPNP_CLASS.get((media_type or "").lower()),
                default_mime_type=content_type,
                meta_data=metadata or {},
            )
            if dev.can_stop:
                try:
                    await dev.async_stop()
                except UpnpError as err:
                    # The Libratone renderer may claim it can stop and then refuse with 701
                    # ("Transition to STOP not allowed"), e.g. while another source is active. Harmless.
                    _LOGGER.debug("%s: ignoring refused Stop before playback: %s", self.speaker.display_name, err)
            await dev.async_set_transport_uri(url, title, didl)
            await dev.async_wait_for_can_play()
            await dev.async_play()
        except UpnpError as err:
            self._device = None   # re-read the description next time
            raise HomeAssistantError(
                f"DLNA playback on {self.speaker.display_name} failed for {url}: {err}"
            ) from err

    async def async_control(self, action: str) -> None:
        """play / pause / stop on the renderer (used while DLNA is the active source)."""
        try:
            dev = await self._get_device()
            await dev.async_update(do_ping=False)
            await {"play": dev.async_play, "pause": dev.async_pause, "stop": dev.async_stop}[action]()
        except UpnpError as err:
            self._device = None
            raise HomeAssistantError(f"DLNA {action} on {self.speaker.display_name} failed: {err}") from err
