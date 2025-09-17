"""The libratone_speaker component."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_NAME
from .const import DOMAIN, PLATFORMS

# Prefer vendored lib during dev. Fall back to PyPI if not present
try:
    from .vendor.python_libratone_zipp.python_libratone_zipp import LibratoneZipp  # type: ignore
except Exception:  # pragma: no cover
    from python_libratone_zipp import LibratoneZipp  # type: ignore

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]

    def _mk():
        z = LibratoneZipp(host)
        try:
            z.name_get(); z.version_get(); z.volume_get()
        except Exception:
            pass
        return z

    zipp = await hass.async_add_executor_job(_mk)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = zipp

    def _on_stop(_event):
        try: zipp.exit()
        except Exception: pass
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    zipp = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if zipp:
        await hass.async_add_executor_job(zipp.exit)
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return unload_ok

