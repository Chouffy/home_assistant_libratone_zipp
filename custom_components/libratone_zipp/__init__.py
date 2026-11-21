"""Libratone Zipp integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_SERIAL, DOMAIN, PLATFORMS
from python_libratone_zipp import LibratoneHub, LibratoneSpeaker

_LOGGER = logging.getLogger(__name__)

IDENTIFY_TIMEOUT = 6.0

type LibratoneConfigEntry = ConfigEntry[LibratoneSpeaker]


async def async_get_hub(hass: HomeAssistant) -> LibratoneHub:
    """Return the shared hub, starting it on first use."""
    data = hass.data.setdefault(DOMAIN, {})
    lock: asyncio.Lock = data.setdefault("hub_lock", asyncio.Lock())
    async with lock:
        hub: LibratoneHub | None = data.get("hub")
        if hub is None:
            hub = LibratoneHub()
            await hub.start()
            data["hub"] = hub

            async def _stop(_event: Event) -> None:
                await hub.stop()

            data["hub_stop_unsub"] = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)
    return hub


def legacy_unique_id(host: str) -> str:
    return "libratone_" + str(host).replace(".", "_").replace(":", "_").lower()


def entity_unique_id(serial: str) -> str:
    return f"libratone_{serial}"


async def _identify(hub: LibratoneHub, spk: LibratoneSpeaker) -> None:
    """Make sure spk has a serial: probe its configured host, else scan for it by name."""
    if spk.serial:
        return
    if await hub.probe(spk.host, timeout=3.0):
        return  # handle_frame stored the serial
    _LOGGER.info("%s not answering at %s, scanning the network for it", spk.display_name, spk.host)
    await hub.scan()
    loop = asyncio.get_running_loop()
    end = loop.time() + IDENTIFY_TIMEOUT
    while spk.serial is None and loop.time() < end:
        await asyncio.sleep(0.25)


async def async_setup_entry(hass: HomeAssistant, entry: LibratoneConfigEntry) -> bool:
    try:
        hub = await async_get_hub(hass)
    except OSError as err:
        raise ConfigEntryNotReady(
            f"Cannot open UDP ports 3333/7778 ({err}). If you just updated the integration, restart Home Assistant."
        ) from err

    serial = entry.data.get(CONF_SERIAL)
    if serial and hub.by_serial(serial):
        _LOGGER.error("Speaker %s is configured twice; ignoring entry %s", serial, entry.title)
        return False

    # v4 entries may store the factory name (e.g. LibratoneZipp1A2B3C) while the title is the
    # real name, so accept both when re-identifying a speaker by name
    spk = hub.add_speaker(
        entry.data[CONF_HOST], serial, entry.title or entry.data.get(CONF_NAME),
        aliases=tuple(n for n in (entry.data.get(CONF_NAME),) if n),
    )
    entry.runtime_data = spk
    from .dlna import LibratoneDlna   # HA-side helper; speaker.py stays HA-free
    spk.dlna = LibratoneDlna(hass, spk)

    async def _fetch_model() -> None:
        if (model := await spk.dlna.async_model()) and model != spk.model:
            spk.model = model
            spk.notify()

    entry.async_create_background_task(hass, _fetch_model(), "libratone_model")

    if not spk.serial:
        await _identify(hub, spk)
        if spk.serial:
            _migrate_to_serial(hass, entry, spk)
        else:
            _LOGGER.warning(
                "Could not find %s (last known at %s); it will be picked up when it comes back",
                spk.display_name, entry.data[CONF_HOST],
            )

    @callback
    def _sync_entry() -> None:
        """Persist host changes; finish the serial migration once a legacy speaker shows up."""
        if spk.host and spk.host != entry.data[CONF_HOST]:
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HOST: spk.host})
        if spk.serial and not entry.data.get(CONF_SERIAL):
            _migrate_to_serial(hass, entry, spk)
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(spk.add_listener(_sync_entry))

    # the read-only color sensor was replaced by a color select
    ent_reg = er.async_get(hass)
    if old := ent_reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_color"):
        ent_reg.async_remove(old)
    _sync_entry()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _migrate_to_serial(hass: HomeAssistant, entry: ConfigEntry, spk: LibratoneSpeaker) -> None:
    """Move a legacy (IP-keyed) entry to serial-keyed ids, keeping entity_ids."""
    assert spk.serial
    other = next(
        (e for e in hass.config_entries.async_entries(DOMAIN)
         if e.entry_id != entry.entry_id and e.unique_id == spk.serial),
        None,
    )
    updates: dict = {"data": {**entry.data, CONF_SERIAL: spk.serial, CONF_HOST: spk.host}}
    if other is None:
        updates["unique_id"] = spk.serial
    hass.config_entries.async_update_entry(entry, **updates)

    ent_reg = er.async_get(hass)
    new_uid = entity_unique_id(spk.serial)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.domain == "media_player" and ent.unique_id != new_uid:
            if ent_reg.async_get_entity_id("media_player", DOMAIN, new_uid):
                continue
            _LOGGER.info("Migrating %s unique_id %s -> %s", ent.entity_id, ent.unique_id, new_uid)
            ent_reg.async_update_entity(ent.entity_id, new_unique_id=new_uid)

    # A device created before the serial was known is keyed by entry_id; re-key it
    # (removing it would also delete its entities and lose the entity_ids).
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    if device is not None and not dev_reg.async_get_device_by_identifier((DOMAIN, spk.serial), entry.entry_id):
        dev_reg.async_update_device(
            device.id, new_identifiers={(DOMAIN, spk.serial)}, serial_number=spk.serial
        )


async def async_unload_entry(hass: HomeAssistant, entry: LibratoneConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    data = hass.data.get(DOMAIN, {})
    hub: LibratoneHub | None = data.get("hub")
    if hub:
        hub.remove_speaker(entry.runtime_data)
        if not hub.speakers:
            unsub = data.pop("hub_stop_unsub", None)
            if unsub:
                unsub()
            await hub.stop()
            data.pop("hub", None)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    return True
