"""The libratone_speaker component."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_NAME
from .const import DOMAIN, PLATFORMS


# Prefer vendored lib during dev. Fall back to PyPI if not present
try:
    from .vendor.python_libratone_zipp.python_libratone_zipp import LibratoneZipp  # type: ignore
except Exception:  # pragma: no cover
    from python_libratone_zipp import LibratoneZipp  # type: ignore

__version__ = "4.0.0"
TARGET_CONFIG_ENTRY_VERSION = 2  # bump this when we change unique_id format

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

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old unique_id formats to the new IP-only form."""
    if entry.version >= TARGET_CONFIG_ENTRY_VERSION:
        return True

    ent_reg = er.async_get(hass)

    for entity_id, e in list(ent_reg.entities.items()):
        if e.config_entry_id != entry.entry_id:
            continue
        old = e.unique_id
        if not old.startswith("libratone_"):
            continue

        parts = old.split("_")
        if len(parts) < 2:
            continue
        # always use the last part (IP tag) only
        ip_tag = parts[-1].lower()
        new_unique_id = f"libratone_{ip_tag}"

        if new_unique_id != old:
            try:
                ent_reg.async_update_entity(e.entity_id, new_unique_id=new_unique_id)
            except ValueError:
                # if collision, skip this one
                continue

    hass.config_entries.async_update_entry(entry, version=TARGET_CONFIG_ENTRY_VERSION)
    return True
