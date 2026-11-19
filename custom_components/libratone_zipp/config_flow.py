"""Config flow: manual IP entry and zeroconf (AirPlay) discovery.

Entries are keyed by the speaker's serial number, so a discovery from a new IP
updates the existing entry instead of being ignored or creating a duplicate.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import async_get_hub
from .const import CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str})


def _clean_name(name: str) -> str:
    """'C467B5000000@LINK Legolas._raop._tcp.local.' -> 'Legolas'."""
    n = name.split("._", 1)[0]
    if "@" in n:
        n = n.split("@", 1)[1]
    if n.upper().startswith("LINK "):
        n = n[5:]
    return n.strip()


class LibratoneConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}

    async def _probe(self, host: str) -> dict | None:
        try:
            hub = await async_get_hub(self.hass)
        except OSError as err:
            _LOGGER.error("Cannot open UDP ports 3333/7778: %s", err)
            return None
        return await hub.probe(host)

    # ------------------------------------------------------------------ manual
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            info = await self._probe(host)
            if info is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["serial"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                name = (user_input.get(CONF_NAME) or "").strip() or info["name"]
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host, CONF_NAME: name, CONF_SERIAL: info["serial"]}
                )
        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    # ------------------------------------------------------------------ zeroconf
    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        host = discovery_info.host
        props = {k.lower(): v for k, v in (discovery_info.properties or {}).items()}
        if (props.get("manufacturer") or "").lower() != "libratone" or ":" in host:
            return self.async_abort(reason="not_libratone")

        serial = props.get("serialnumber")
        name = props.get("fn") or _clean_name(discovery_info.name)
        if not serial:
            info = await self._probe(host)
            if info is None:
                return self.async_abort(reason="cannot_connect")
            serial, name = info["serial"], info["name"]

        # Known speaker (possibly at a new IP, or advertising as "LINK <name>" while grouped)
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Legacy entries (pre-serial) are keyed by IP and fix themselves on setup; don't offer a duplicate
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_SERIAL) is None and (entry.title or "").casefold() == name.casefold():
                return self.async_abort(reason="already_configured")

        self._discovered = {CONF_HOST: host, CONF_NAME: name, CONF_SERIAL: serial}
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=self._discovered[CONF_NAME], data=self._discovered)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._discovered[CONF_NAME], "host": self._discovered[CONF_HOST]},
        )
