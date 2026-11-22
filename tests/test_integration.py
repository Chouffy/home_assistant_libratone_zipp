"""End-to-end tests against fake speakers on loopback addresses."""
from __future__ import annotations

import asyncio
import json
from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.libratone_zipp.const import CONF_SERIAL, DOMAIN
from python_libratone_zipp.protocol import Cmd

from .fake_speaker import SPOTIFY_PLAYER

LEGOLAS = "1234-H0032000-07-00001"
ARWEN = "1234-H0032000-07-00002"


async def wait_for(predicate, timeout: float = 8.0) -> None:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.05)


def entry_for(host: str, name: str, serial: str | None = None) -> MockConfigEntry:
    data = {"host": host, "name": name}
    if serial:
        data[CONF_SERIAL] = serial
    return MockConfigEntry(domain=DOMAIN, title=name, unique_id=serial or host, data=data)


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_legacy_entry_with_stale_ip_is_found_and_migrated(hass: HomeAssistant, fakes) -> None:
    """The real-world bug: entry says .26 (old DHCP lease), speaker now lives elsewhere."""
    await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player=SPOTIFY_PLAYER)
    # exactly like the real v4 entry: title Legolas, stored name = factory name, unique_id = IP
    entry = MockConfigEntry(domain=DOMAIN, title="Legolas", unique_id="127.0.0.26",
                            data={"host": "127.0.0.26", "name": "LibratoneZipp1A2B3C"})
    ent_reg = er.async_get(hass)
    entry.add_to_hass(hass)
    ent_reg.async_get_or_create(
        "media_player", DOMAIN, "libratone_127_0_0_26", config_entry=entry,
        suggested_object_id="libratonezipp1a2b3c",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data["host"] == "127.0.0.3"
    assert entry.data[CONF_SERIAL] == LEGOLAS
    assert entry.unique_id == LEGOLAS
    # entity_id kept, unique_id moved to the serial
    ent = ent_reg.async_get("media_player.libratonezipp1a2b3c")
    assert ent is not None and ent.unique_id == f"libratone_{LEGOLAS}"

    await wait_for(lambda: hass.states.get("media_player.libratonezipp1a2b3c").state == "playing")
    attrs = hass.states.get("media_player.libratonezipp1a2b3c").attributes
    assert attrs["media_title"] == "Sweet Child O' Mine"
    assert attrs["media_artist"] == "Guns N' Roses"
    assert attrs["media_album_name"] == "Appetite For Destruction"
    assert attrs["media_playlist"] == "Don't Stop Believin' Radio"
    assert attrs["source"] == "Spotify"
    assert attrs["sound_mode"] == "Rock the house"
    assert attrs["volume_level"] == 0.16
    assert attrs["source_list"][0] == "1: BBC Radio 6 Music"
    assert "entity_picture" in attrs


async def test_speaker_changes_ip_while_running(hass: HomeAssistant, fakes) -> None:
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    entry = entry_for("127.0.0.2", "Arwen", ARWEN)
    await setup(hass, entry)
    entity_id = "media_player.arwen"
    await wait_for(lambda: hass.states.get(entity_id).state == "playing")

    await arwen.move("127.0.0.5")       # speaker sleeps, comes back with a new lease
    await wait_for(lambda: hass.states.get(entity_id).state == "unavailable")
    await wait_for(lambda: entry.data["host"] == "127.0.0.5")
    await wait_for(lambda: hass.states.get(entity_id).state == "playing")


async def test_unavailable_then_back_on_same_ip(hass: HomeAssistant, fakes) -> None:
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "playing")
    arwen.stop()
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "unavailable")
    await arwen.start("127.0.0.2")
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "playing")


async def test_controls(hass: HomeAssistant, fakes) -> None:
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    eid = "media_player.arwen"
    await wait_for(lambda: hass.states.get(eid).state == "playing")

    await hass.services.async_call("media_player", "volume_set", {"entity_id": eid, "volume_level": 0.3}, blocking=True)
    await hass.services.async_call("media_player", "select_sound_mode", {"entity_id": eid, "sound_mode": "Neutral"}, blocking=True)
    await hass.services.async_call("media_player", "select_source", {"entity_id": eid, "source": "3: Radio Paradise"}, blocking=True)
    await hass.services.async_call("media_player", "media_pause", {"entity_id": eid}, blocking=True)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.arwen_room_placement", "option": "Neutral"}, blocking=True)
    await hass.services.async_call("media_player", "turn_off", {"entity_id": eid}, blocking=True)

    await wait_for(lambda: arwen.sets(Cmd.TIMER))  # UDP is async; wait for the last command
    assert arwen.sets(Cmd.VOLUME) == ["30"]
    assert arwen.sets(Cmd.VOICING_SET) == ["V100"]
    assert '"play_identity":"3"' in arwen.sets(Cmd.PLAYER_SET)[0]
    assert arwen.sets(Cmd.PLAY_CONTROL) == ["PAUSE"]
    assert arwen.sets(Cmd.ROOM_SET) == ["neutral"]
    assert arwen.sets(Cmd.TIMER) == ["20"]
    await wait_for(lambda: hass.states.get(eid).state == "off")
    assert hass.states.get("select.arwen_room_placement").state == "Neutral"
    assert hass.states.get("sensor.arwen_battery").state == "100"


async def test_grouping(hass: HomeAssistant, fakes) -> None:
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player=SPOTIFY_PLAYER)
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "playing")

    # join from HA: both get 502 with an app-style link id
    await hass.services.async_call("media_player", "join",
                                   {"entity_id": "media_player.legolas", "group_members": ["media_player.arwen"]},
                                   blocking=True)
    await wait_for(lambda: legolas.sets(Cmd.GROUP_JOIN) and arwen.sets(Cmd.GROUP_JOIN))
    link = legolas.sets(Cmd.GROUP_JOIN)[0]
    assert link.startswith(f"LINK Legolas_{LEGOLAS}-2002_")  # app format incl. color
    assert arwen.sets(Cmd.GROUP_JOIN) == [link]

    # speakers confirm with notifications; only "GROUPED" first -> master inferred from link id
    link_id = link[5:]
    legolas.set_group("M", link_id)
    arwen.set_group("S", link_id)
    for fake in (legolas, arwen):
        fake.notify(Cmd.GROUP, f"GROUPED,{link}")
    await wait_for(lambda: hass.states.get("media_player.arwen").attributes.get("group_members")
                   == ["media_player.legolas", "media_player.arwen"])
    # the slave shows the master's media
    assert hass.states.get("media_player.arwen").attributes["media_title"] == "Sweet Child O' Mine"

    # unjoin a pair -> both leave, FREE clears the group
    await hass.services.async_call("media_player", "unjoin", {"entity_id": "media_player.arwen"}, blocking=True)
    await wait_for(lambda: arwen.sets(Cmd.GROUP_LEAVE) and legolas.sets(Cmd.GROUP_LEAVE))
    assert arwen.sets(Cmd.GROUP_LEAVE) == [link] and legolas.sets(Cmd.GROUP_LEAVE) == [link]
    for fake in (legolas, arwen):
        fake.set_group("F")
        fake.notify(Cmd.GROUP, "FREE")
    await wait_for(lambda: hass.states.get("media_player.arwen").attributes.get("group_members") is None)
    assert hass.states.get("media_player.arwen").attributes.get("media_title") is None


async def test_config_flow_user_and_zeroconf_host_update(hass: HomeAssistant, fakes) -> None:
    await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "127.0.0.2"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Arwen"
    assert result["data"] == {"host": "127.0.0.2", "name": "Arwen", CONF_SERIAL: ARWEN}
    entry = result["result"]
    assert entry.unique_id == ARWEN
    await hass.async_block_till_done()

    # unreachable host -> error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "127.0.0.99"})
    assert result["errors"] == {"base": "cannot_connect"}

    # zeroconf sees the same serial on a new IP (e.g. advertised as "LINK Arwen") -> host updated
    ip = ip_address("127.0.0.7")
    info = ZeroconfServiceInfo(
        ip_address=ip, ip_addresses=[ip], port=7000, hostname="Arwen.local.", type="_airplay._tcp.local.",
        name="LINK Arwen._airplay._tcp.local.",
        properties={"manufacturer": "Libratone", "serialNumber": ARWEN, "model": "LTH300"},
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert entry.data["host"] == "127.0.0.7"
    await hass.async_block_till_done()


async def test_zeroconf_new_speaker(hass: HomeAssistant) -> None:
    ip = ip_address("127.0.0.8")
    info = ZeroconfServiceInfo(
        ip_address=ip, ip_addresses=[ip], port=7000, hostname="Legolas.local.", type="_airplay._tcp.local.",
        name="Legolas._airplay._tcp.local.",
        properties={"manufacturer": "Libratone", "serialNumber": LEGOLAS},
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "127.0.0.8", "name": "Legolas", CONF_SERIAL: LEGOLAS}
    await hass.async_block_till_done()


async def test_group_state_known_without_notifications(hass: HomeAssistant, fakes) -> None:
    """Linked before HA started (no 103 notification ever arrives): LSSDP polling must find the group."""
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player=SPOTIFY_PLAYER)
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    link_id = f"Legolas_{LEGOLAS}_1353413036"
    legolas.set_group("M", link_id)
    arwen.set_group("S", link_id)
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))

    await wait_for(lambda: hass.states.get("media_player.arwen").attributes.get("group_members")
                   == ["media_player.legolas", "media_player.arwen"])
    assert hass.states.get("media_player.legolas").attributes["group_role"] == "MASTER"
    assert hass.states.get("media_player.arwen").attributes["group_role"] == "SLAVE"
    assert hass.states.get("media_player.arwen").attributes["group_link_id"] == link_id
    assert hass.states.get("media_player.arwen").attributes["media_title"] == "Sweet Child O' Mine"

    # linked but idle: both report "G" (grouped, no roles yet) -> master inferred from the link id
    legolas.set_group("G", link_id)
    arwen.set_group("G", link_id)
    await wait_for(lambda: hass.states.get("media_player.arwen").attributes.get("group_role") == "GROUPED")
    await wait_for(lambda: hass.states.get("media_player.legolas").attributes.get("group_role") == "GROUPED")
    assert hass.states.get("media_player.arwen").attributes["group_members"] == ["media_player.legolas", "media_player.arwen"]

    # unlinked in the app while HA wasn't listening -> next poll clears it
    legolas.set_group("F")
    arwen.set_group("F")
    await wait_for(lambda: hass.states.get("media_player.arwen").attributes.get("group_members") is None)
    assert hass.states.get("media_player.legolas").attributes["group_role"] is None


async def test_lssdp_is_not_a_sign_of_life(hass: HomeAssistant, fakes) -> None:
    """A hung speaker still answered LSSDP: that must not keep it 'available'."""
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "playing")
    await wait_for(lambda: arwen.lssdp_queries > 0)
    arwen._transport.close()            # control service dies, LSSDP keeps answering
    arwen._transport = None
    await wait_for(lambda: hass.states.get("media_player.arwen").state == "unavailable")


async def test_stereo_channel(hass: HomeAssistant, fakes) -> None:
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    eid = "select.legolas_audio_channel"
    await wait_for(lambda: hass.states.get(eid).state == "stereo")   # read via LSSDP (GET 512 is empty)
    for option, code in (("left", "1"), ("right", "2"), ("stereo", "0")):
        await hass.services.async_call("select", "select_option", {"entity_id": eid, "option": option}, blocking=True)
        await wait_for(lambda: legolas.sets(Cmd.CHANNEL)[-1:] == [code])
        await wait_for(lambda: hass.states.get(eid).state == option)
    # changed in the app while HA is running: LSSDP poll picks it up
    legolas.channel = "R"
    await wait_for(lambda: hass.states.get(eid).state == "right")


async def test_master_inferred_from_app_link_id_with_color(hass: HomeAssistant, fakes) -> None:
    """The app's link ids carry the color: <Name>_<Serial>-<Color>_<rand>."""
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas")
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen", player=SPOTIFY_PLAYER)
    link_id = f"Arwen_{ARWEN}-2002_1244746321"
    legolas.set_group("G", link_id)
    arwen.set_group("G", link_id)
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    await wait_for(lambda: hass.states.get("media_player.legolas").attributes.get("group_members")
                   == ["media_player.arwen", "media_player.legolas"])
    assert hass.states.get("media_player.legolas").attributes["media_title"] == "Sweet Child O' Mine"

    # and HA's own joins now use the same shape
    await hass.services.async_call("media_player", "unjoin", {"entity_id": "media_player.legolas"}, blocking=True)
    await hass.services.async_call("media_player", "join",
                                   {"entity_id": "media_player.legolas", "group_members": ["media_player.arwen"]},
                                   blocking=True)
    await wait_for(lambda: any(t.startswith("LINK Legolas_") for t in arwen.sets(Cmd.GROUP_JOIN)))
    new = [t for t in arwen.sets(Cmd.GROUP_JOIN) if t.startswith("LINK Legolas_")][0]
    assert new.startswith(f"LINK Legolas_{LEGOLAS}-2002_")


async def test_bluetooth_playback_shows_as_playing(hass: HomeAssistant, fakes) -> None:
    """Real values from Legolas: Bluetooth playing -> cmd 51 says paused, cmd 10 byte 2 = 08, LSSDP P."""
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas")
    legolas.values[Cmd.PLAY_STATUS] = "2"
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("410c0833000000")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    eid = "media_player.legolas"
    await wait_for(lambda: hass.states.get(eid).state == "playing")
    assert hass.states.get(eid).attributes["source"] == "Bluetooth"

    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("410c0333000000")   # paused on the phone
    await wait_for(lambda: hass.states.get(eid).state == "paused")
    assert hass.states.get(eid).attributes.get("source") is None


async def test_radio_favorite_source(hass: HomeAssistant, fakes) -> None:
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player={
        "isFromChannel": True, "play_identity": "3", "play_title": "Radio Paradise",
        "play_subtitle": "", "play_token": "", "play_type": "channel"})
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("3f100045030000")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    eid = "media_player.legolas"
    await wait_for(lambda: hass.states.get(eid).state == "playing")
    assert hass.states.get(eid).attributes["source"] == "3: Radio Paradise"
    assert hass.states.get(eid).attributes["media_title"] == "Radio Paradise"


def _timer(seconds: int) -> bytes:
    return b"2" + seconds.to_bytes(2, "little") + b"\x00\x00"


async def test_sleep_timer(hass: HomeAssistant, fakes) -> None:
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    eid = "number.arwen_sleep_timer"
    await wait_for(lambda: hass.states.get(eid).state == "0")
    await hass.services.async_call("number", "set_value", {"entity_id": eid, "value": 10}, blocking=True)
    await wait_for(lambda: arwen.sets(Cmd.TIMER)[-1:] == ["2600"])
    await wait_for(lambda: hass.states.get(eid).state == "10")
    arwen.values[Cmd.TIMER] = _timer(594)                    # counting down: rounds up to 10 min
    await wait_for(lambda: hass.states.get(eid).state == "10")
    arwen.values[Cmd.TIMER] = _timer(539)
    await wait_for(lambda: hass.states.get(eid).state == "9")
    await hass.services.async_call("number", "set_value", {"entity_id": eid, "value": 0}, blocking=True)
    await wait_for(lambda: arwen.sets(Cmd.TIMER)[-1:] == ["F0"])
    await wait_for(lambda: hass.states.get(eid).state == "0")
    assert hass.states.get("media_player.arwen").state == "playing"    # never put to sleep


async def test_save_favorite(hass: HomeAssistant, fakes) -> None:
    """Like the app's '+': SET 276 with the playing station (real payload shape from session 21-favorite)."""
    import json

    import pytest
    from homeassistant.exceptions import ServiceValidationError

    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player={
        "isFromChannel": True, "play_identity": "3", "play_title": "Radio Paradise",
        "play_subtitle": "", "play_token": "", "play_type": "channel"})
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("3f100045030000")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    eid = "media_player.legolas"
    await wait_for(lambda: hass.states.get(eid).attributes.get("source") == "3: Radio Paradise")

    await hass.services.async_call(DOMAIN, "save_favorite", {"entity_id": eid, "slot": 1}, blocking=True)
    await wait_for(lambda: legolas.sets(Cmd.CHANNEL_SAVE))
    assert json.loads(legolas.sets(Cmd.CHANNEL_SAVE)[0]) == {
        "channel_id": 1, "channel_identity": "1003", "channel_name": "Radio Paradise",
        "channel_type": "vtuner", "isPlaying": False}
    await wait_for(lambda: hass.states.get(eid).attributes["source_list"][0] == "1: Radio Paradise")

    # Spotify playing: nothing to save
    legolas.values[Cmd.PLAYER] = json.dumps(SPOTIFY_PLAYER)
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("340c00f3040000")
    await wait_for(lambda: hass.states.get(eid).attributes.get("source") == "Spotify")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "save_favorite", {"entity_id": eid, "slot": 2}, blocking=True)
    assert len(legolas.sets(Cmd.CHANNEL_SAVE)) == 1


async def test_play_media_via_dlna(hass: HomeAssistant, fakes) -> None:
    from unittest.mock import AsyncMock, patch

    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas")
    with patch("custom_components.libratone_zipp.dlna.LibratoneDlna.async_play", new=AsyncMock()) as play:
        await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
        eid = "media_player.legolas"
        await wait_for(lambda: hass.states.get(eid).state == "playing")
        await hass.services.async_call("media_player", "play_media", {
            "entity_id": eid, "media_content_id": "http://stream.example/radio.mp3",
            "media_content_type": "music", "extra": {"title": "Test stream", "thumb": "http://img.example/c.jpg"},
        }, blocking=True)
        play.assert_awaited_once()
        url, title, mtype = play.await_args.args[:3]
        assert (url, title, mtype) == ("http://stream.example/radio.mp3", "Test stream", "music")
    # the speaker switches to DLNA mode (0x32, real value) with an empty player
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("321700c7030000")
    legolas.values[Cmd.PLAYER] = json.dumps({"isFromChannel": False, "play_type": "channel", "play_identity": ""})
    await wait_for(lambda: hass.states.get(eid).attributes.get("source") == "DLNA")
    attrs = hass.states.get(eid).attributes
    assert attrs["media_title"] == "Test stream"
    assert "entity_picture" in attrs


async def test_save_favorite_select(hass: HomeAssistant, fakes) -> None:
    legolas = await fakes("127.0.0.3", serial=LEGOLAS, name="Legolas", player={
        "isFromChannel": True, "play_identity": "3", "play_title": "Radio Paradise",
        "play_subtitle": "", "play_token": "", "play_type": "channel"})
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("3f100045030000")
    await setup(hass, entry_for("127.0.0.3", "Legolas", LEGOLAS))
    eid = "select.legolas_save_playing_station_as_favorite"
    await wait_for(lambda: hass.states.get(eid).state == "unknown")       # available, nothing selected
    assert hass.states.get(eid).attributes["options"][0] == "1: BBC Radio 6 Music"
    await hass.services.async_call("select", "select_option", {"entity_id": eid, "option": "1: BBC Radio 6 Music"},
                                   blocking=True)
    await wait_for(lambda: legolas.sets(Cmd.CHANNEL_SAVE))
    assert json.loads(legolas.sets(Cmd.CHANNEL_SAVE)[0])["channel_id"] == 1
    await wait_for(lambda: hass.states.get(eid).attributes["options"][0] == "1: Radio Paradise")
    # Spotify playing -> nothing to save -> unavailable
    legolas.values[Cmd.PLAYER] = json.dumps(SPOTIFY_PLAYER)
    legolas.values[Cmd.SOURCE_STATE] = bytes.fromhex("340c00f3040000")
    await wait_for(lambda: hass.states.get(eid).state == "unavailable")


async def test_name_color_diagnostics_and_device(hass: HomeAssistant, fakes) -> None:
    from homeassistant.helpers import device_registry as dr

    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    eid = "select.arwen_color"
    await wait_for(lambda: hass.states.get(eid).state == "Graphite Grey")
    assert hass.states.get(eid).attributes["hex"] == "#4f4f4f"
    await hass.services.async_call("select", "select_option", {"entity_id": eid, "option": "Pastel Blue"}, blocking=True)
    await wait_for(lambda: arwen.sets(Cmd.COLOR_SET) == ["2009"])
    await wait_for(lambda: hass.states.get(eid).state == "Pastel Blue")

    await wait_for(lambda: hass.states.get("sensor.arwen_wifi_network").state == "FRITZ!Box 7272")
    assert hass.states.get("sensor.arwen_wifi_signal").state == "100"            # "5/5" bars
    assert hass.states.get("sensor.arwen_ip_address").state == "127.0.0.2"

    # mute set on the speaker (touch panel held) -> read-only binary sensor
    await wait_for(lambda: hass.states.get("binary_sensor.arwen_muted").state == "off")
    arwen.notify(Cmd.PRIVATE_MODE, "1")      # pushed immediately by the real speaker
    await wait_for(lambda: hass.states.get("binary_sensor.arwen_muted").state == "on")
    arwen.values[Cmd.PRIVATE_MODE] = "0"     # released: next poll
    await wait_for(lambda: hass.states.get("binary_sensor.arwen_muted").state == "off")

    # rename on the speaker
    await wait_for(lambda: hass.states.get("text.arwen_speaker_name").state == "Arwen")
    await hass.services.async_call("text", "set_value", {"entity_id": "text.arwen_speaker_name", "value": "Arwen-test"},
                                   blocking=True)
    await wait_for(lambda: arwen.sets(Cmd.NAME) == ["Arwen-test"])
    await wait_for(lambda: hass.states.get("text.arwen_speaker_name").state == "Arwen-test")

    # device: MAC from LSSDP DeviceID, link to the speaker's web UI
    dev = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, ARWEN), hass.config_entries.async_entries(DOMAIN)[0].entry_id)
    await wait_for(lambda: (dr.CONNECTION_NETWORK_MAC, "c4:67:b5:00:00:00")
                   in dr.async_get(hass).async_get(dev.id).connections)
    assert dr.async_get(hass).async_get(dev.id).configuration_url == "http://127.0.0.2/"


async def test_favorite_started_event(hass: HomeAssistant, fakes) -> None:
    """Heart button on the speaker: it pushes NOTIFY 278 with isFromChannel + slot (real payload shape)."""
    arwen = await fakes("127.0.0.2", serial=ARWEN, name="Arwen")
    await setup(hass, entry_for("127.0.0.2", "Arwen", ARWEN))
    eid = "event.arwen_favorite_started"
    await wait_for(lambda: hass.states.get(eid) is not None and hass.states.get(eid).state != "unavailable")

    pressed = {"isFromChannel": True, "play_identity": "2", "play_subtitle": "", "play_title": "BBC Radio 4",
               "play_token": "", "play_type": "channel"}
    arwen.notify(Cmd.PLAYER, json.dumps(pressed))
    await wait_for(lambda: hass.states.get(eid).attributes.get("event_type") == "favorite_2")
    attrs = hass.states.get(eid).attributes
    assert attrs["name"] == "BBC Radio 4" and attrs["started_by"] == "speaker_or_app"

    # started from Home Assistant: same notification, but marked as ours
    await hass.services.async_call("media_player", "select_source",
                                   {"entity_id": "media_player.arwen", "source": "3: Radio Paradise"}, blocking=True)
    arwen.notify(Cmd.PLAYER, json.dumps(dict(pressed, play_identity="3", play_title="Radio Paradise")))
    await wait_for(lambda: hass.states.get(eid).attributes.get("event_type") == "favorite_3")
    assert hass.states.get(eid).attributes["started_by"] == "home_assistant"
