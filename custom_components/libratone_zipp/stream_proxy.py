"""Relay https streams to the speaker over plain http.

The Libratone firmware can't open current https servers (SetAVTransportURI fails with UPnP error 716
"resource is not found"; the same stations work over http). Home Assistant fetches the https stream and
serves it to the speaker at http://<HA>/api/libratone_zipp/stream/<token>, like it already serves TTS.
Only URLs registered by this integration are relayed (random token per URL, small LRU).
"""
from __future__ import annotations

from collections import OrderedDict
import logging
import secrets

import aiohttp
from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_STREAMS = f"{DOMAIN}_streams"
MAX_STREAMS = 20
CHUNK = 8192


@callback
def async_register(hass: HomeAssistant) -> None:
    if DATA_STREAMS not in hass.data:
        hass.data[DATA_STREAMS] = OrderedDict()
        hass.http.register_view(StreamProxyView())


@callback
def async_proxy_url(hass: HomeAssistant, url: str) -> str:
    """http URL on Home Assistant that relays `url`."""
    streams: OrderedDict[str, str] = hass.data[DATA_STREAMS]
    token = secrets.token_urlsafe(16)
    streams[token] = url
    while len(streams) > MAX_STREAMS:
        streams.popitem(last=False)
    base = get_url(hass, allow_external=False, allow_cloud=False, prefer_external=False)
    return f"{base}/api/{DOMAIN}/stream/{token}"


class StreamProxyView(HomeAssistantView):
    url = f"/api/{DOMAIN}/stream/{{token}}"
    name = f"api:{DOMAIN}:stream"
    requires_auth = False   # the speaker can't authenticate; the random token is the access control

    def _target(self, request: web.Request, token: str) -> str | None:
        return request.app[KEY_HASS].data.get(DATA_STREAMS, {}).get(token)

    async def head(self, request: web.Request, token: str) -> web.StreamResponse:
        if (target := self._target(request, token)) is None:
            return web.Response(status=404)
        session = async_get_clientsession(request.app[KEY_HASS])
        try:
            async with session.get(target, timeout=aiohttp.ClientTimeout(sock_connect=10, sock_read=15)) as up:
                return web.Response(status=up.status, headers={"Content-Type": up.headers.get("Content-Type", "audio/mpeg")})
        except (aiohttp.ClientError, TimeoutError):
            return web.Response(status=502)

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        if (target := self._target(request, token)) is None:
            return web.Response(status=404)
        session = async_get_clientsession(request.app[KEY_HASS])
        resp: web.StreamResponse | None = None
        try:
            async with session.get(target, timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60)) as up:
                resp = web.StreamResponse(status=up.status)
                resp.headers["Content-Type"] = up.headers.get("Content-Type", "audio/mpeg")
                await resp.prepare(request)
                async for chunk in up.content.iter_chunked(CHUNK):
                    await resp.write(chunk)
        except (ConnectionResetError, aiohttp.ClientConnectionResetError):
            _LOGGER.debug("Speaker closed the stream for %s", target)   # normal when playback stops
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Relaying %s failed: %s", target, err)
            if resp is None:
                return web.Response(status=502)
        return resp if resp is not None else web.Response(status=502)
