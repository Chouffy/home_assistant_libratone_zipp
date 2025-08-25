from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from .const import DOMAIN

# Prefer vendored lib during dev. Fall back to PyPI if not present
try:
    from .vendor.python_libratone_zipp.python_libratone_zipp import LibratoneZipp  # type: ignore
except Exception:  # pragma: no cover
    from python_libratone_zipp import LibratoneZipp  # type: ignore

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_NAME): str,
})

async def _probe(hass: HomeAssistant, host: str) -> dict[str, Any]:
    """Create a client, fetch minimal identity, then close it."""
    def _run():
        z = LibratoneZipp(host)
        try:
            z.name_get(); z.version_get(); z.serialnumber_get()
        except Exception:
            pass
        info = {
            "name": getattr(z, "name", None),
            "serial": getattr(z, "serialnumber", None),
            "version": getattr(z, "version", None),
        }
        try:
            z.exit()
        except Exception:
            pass
        return info
    return await hass.async_add_executor_job(_run)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        host = user_input[CONF_HOST].strip()
        name = (user_input.get(CONF_NAME) or "").strip() or None

        try:
            info = await _probe(self.hass, host)
        except Exception:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        unique = info.get("serial") or host
        await self.async_set_unique_id(unique)
        self._abort_if_unique_id_configured()

        title = name or info.get("name") or f"Libratone {host}"
        data = {CONF_HOST: host, CONF_NAME: name or info.get("name") or title}
        return self.async_create_entry(title=title, data=data)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Optional: handles YAML import later if you decide to migrate."""
        return await self.async_step_user(user_input)
