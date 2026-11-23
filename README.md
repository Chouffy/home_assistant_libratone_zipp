# Libratone Zipp controller for Home Assistant

This controls Libratone Zipp speakers from [Home Assistant](https://www.home-assistant.io/).

It uses [python_libratone_zipp](https://github.com/Chouffy/python_libratone_zipp) 5.x (asyncio) for the speaker protocol.
Speakers are identified by **serial number**, not IP: when a speaker comes back from sleep/power-off with a new DHCP address, the integration finds it again by itself (zeroconf, plus a small UDP sweep of the subnet while a speaker is missing).

## Limitations / Known bugs

* Sources can't be switched from Home Assistant except the five favorites and media started from Home Assistant
  (DLNA). The app can't either: Spotify is controlled via Spotify Connect, Bluetooth from the phone.
  They are detected though, see [Sources](#sources).
* Bluetooth: playback is detected (shown as playing, source "Bluetooth"), whether a phone is *connected* is not.
  Bluetooth has its own volume, which the speaker doesn't report.
* Favorites stored on the speaker can only be vTuner stations (and Spotify via the app): a stream URL can be
  saved but the speaker won't play it (tested). Stations from Home Assistant play via DLNA instead, see
  [Favorites from the heart button](#favorites-from-the-heart-button).
* Mute is read-only (`binary_sensor.<speaker>_muted`): the speaker mutes itself when its touch panel is held,
  there is no network command to set it.
* The integration needs UDP ports `7778` and `3333` (the speakers always answer to these) and uses UDP `1800`
  (LSSDP status) and TCP `49152` (the speaker's DLNA renderer) on the speakers.

## Usage

### Installation via [HACS](https://hacs.xyz/)

1. Search for *Libratone Zipp* in the integration tab of HACS
1. Click *Install*
1. Restart Home Assistant
1. Go to _Settings_ → _Devices & services_ → _Add integration_ and search for **Libratone Zipp**
1. Add the IP of the speaker and a name
1. Repeat the last step if you have multiple speakers

Note: if you're using Docker/devcontainer, you need to forward `3333/udp` and `7778/udp`. 

## Features

### Functionality coverage

Current coverage suits me, even if the python integration has much more options. Don't expect new features (only maintenance) but feel free to open an issue or submit a PR!

* v1.0
    * [x] Set up entity in home assistant
    * [x] Basic playback status
    * [x] Calculate status
* v2.0
    * [x] Set a sound mode (voicing)
    * [x] Use human names for Voicing / Sound mode
    * [x] Retrieve basic playback status: play, pause, stop, next, prev
    * [x] Set volume
    * [x] Retrieve volume
    * [x] Set to immediate standby (sleep)
    * [x] Retrieve current Voicing
    * [x] (kinda) Play a favorite (but it's only number)
* v3.0
    * [x] Retrieve current title and sub-title
* v4.0
    * [x] Manage multiple speakers
    * [x] Add/Remove speakers via Web interface (no `configuration.yaml` anymore!)
* v4.1 
    * [x] Implement SoundSpace Link
* v5.0
    * [x] Async, based on python_libratone_zipp 5.0 (asyncio)
    * [x] Speakers tracked by serial number; automatic recovery after IP changes, proper `unavailable` state
    * [x] Push updates instead of 5 s polling
    * [x] Artist, album, playlist, cover art, current source (Spotify, favorite name, ...)
    * [x] Favorites by name, room placement select, battery sensor, device entries
    * [x] Group members master-first, slave mirrors the master's media, app-compatible link ids
    * [x] Group state polled from the speakers' LSSDP status (UDP 1800): correct right after an HA restart
    * [x] Audio channel select (stereo / left / right)
    * [x] Source detection incl. Bluetooth; Bluetooth playback shows as playing (was: only "Play" button)
    * [x] Play media / media browser / TTS through the speaker's own DLNA renderer (one entity instead of two)
    * [x] Sleep timer, save favorite, rename, color, mute (read-only), WiFi / IP diagnostics


Roadmap (status after v5, 2026-11-21). Open points are free to take: PRs welcome!

* Module
    * [x] Make the module async
    * [ ] Submit it for official integration!
    * [ ] Add support for other libratone speakers (see [Help wanted](#help-wanted-other-libratone-speakers))
* Current Playback info
    * [x] Retrieve current playback source
    * [x] Retrieve media type: see [Sources](#sources) for what is tested
* Standby
    * [x] Set a standby (sleep) timer: `number.<speaker>_sleep_timer`, minutes, 0 = off
    * [x] Retrieve a standby timer (shows the remaining time, counts down)
* Voicing & Room Setting
    * [x] Set Room Setting (`select.<speaker>_room_placement`)
    * [x] Retrieve current Room Setting
* Favorites
    * [x] Play a favorite (proper title, from the speaker's favorite list)
    * [x] Set a Favorite: service `libratone_zipp.save_favorite` (slot 1-5) saves the radio station playing now
* Extended current playback info
    * [ ] Set / retrieve shuffle, repeat (not exposed by the speaker; Spotify controls it)
    * [ ] Set Source (not possible; the app can't either, except the favorites)
    * [x] Retrieve current source
* Multi-room
    * [x] Set speaker mode (stereo, left, right): `select.<speaker>_audio_channel`
    * [x] Group state that survives restarts (LSSDP)
    * [x] One media player for control and media (DLNA), no second entity needed
* One player instead of two (Libratone + DLNA)
    * [x] Register the speaker's MAC (LSSDP `DeviceID`) as device connection (note: current HA versions no longer merge devices across integrations)
    * [x] `play_media` + media browser via the speaker's own UPnP renderer (AVTransport on :49152, `async-upnp-client`):
          local media, Radio Browser, TTS. The separate DLNA entity isn't needed any more
* Other models
    * [x] Model from the speaker's UPnP description (`LTH300` -> Zipp) instead of a fixed "Zipp"
    * [ ] Test Zipp Mini (v5 features) / Zipp 2 / Zipp Mini 2
* Colors and names
    * [x] Read and set the color (`select.<speaker>_color`, all 15 colors mapped, SET 771 verified)
    * [x] Rename the speaker (`text.<speaker>_speaker_name`, SET 90, verified)
* Speaker
    * [x] Mute state, read-only (`binary_sensor.<speaker>_muted`)
    * [ ] Auto-standby time (cmd 528 reads `300`; the app has no setting for it)
* Network and diagnostics
    * [x] WiFi signal, WiFi network, IP address as diagnostic sensors; firmware, MAC and a link to the speaker's web UI on the device page
    * [ ] Bluetooth: connection state / pairing (not visible on the network side so far)
* Firmware, setup and factory reset (in case Libratone's app/servers go away) - contributions welcome
    * [ ] Firmware update: show "update available" / progress (the speakers push JSON on cmd 65; the web UI has `cgi?Update` incl. local upload)
    * [ ] WiFi setup through the speaker's own web UI (`cgi?Network` -> `cgi?SetNet`), incl. a factory-new speaker's setup hotspot (needs a capture)
    * [ ] Factory reset (`SET 150`, known; deliberately not exposed yet)
* Radio
    * [x] Favorites: play by name, save the playing station (`select.<speaker>_save_playing_station_as_favorite` or `libratone_zipp.save_favorite`)
    * [ ] Save Spotify content as a favorite (the app can; needs a capture)
    * [x] Notice favorites started with the heart button / app (`event.<speaker>_favorite_started`)
    * [ ] Any stream as a favorite on the speaker itself: not possible (only vTuner ids play); use the event + an automation
    * [x] Any station: via `play_media` / media browser (e.g. Radio Browser), independent of vTuner/Libratone

## When a speaker gets a new IP address

Speakers are identified by serial number, not IP. When a speaker comes back with a new address (sleep,
power off, new DHCP lease), Home Assistant finds it again by itself, without scanning the network:

* **DHCP discovery**: Home Assistant notices the speaker requesting an address (Libratone MAC prefix `C4:67:B5`).
* **LSSDP**: every speaker, also a group slave, announces itself on UDP port 1800 about every 10 s. The integration
  listens, and while a speaker is missing it sends one search request (a single broadcast, like the Libratone app).
* **Zeroconf** (AirPlay announcement), as before.

**Optional: active search (UDP sweep), off by default.** If none of the above reaches Home Assistant, typically
**Home Assistant in Docker without host networking** (broadcasts and DHCP traffic don't reach the container), you
can turn on *Actively search the network if the speaker can't be found* under *Configure* on the speaker. While the
speaker is missing, the integration then sends a small query (2 UDP packets of ~10 bytes) to every address of the
speaker's /24 network on port 7777, once a minute (every 5 minutes after 10 minutes). Only Libratone speakers
answer. It is not a port scan, but network monitoring may still see it as a scan, which is why it's opt-in.

## Favorites from the heart button

`event.<speaker>_favorite_started` fires whenever a favorite starts: chosen with the heart button on the
speaker, in the app, or from Home Assistant. Event types `favorite_1` ... `favorite_5`, with the attributes
`name` and `started_by` (`speaker_or_app` or `home_assistant`). It fires also for favorites that then fail
to play (dead vTuner stations).

Why this exists:

1. **Favorites the speaker can't store.** The speaker only plays vTuner stations as favorites. With this event
   the heart button can start anything Home Assistant can play (Radio Browser, local media, ...), without
   reaching for the app or Home Assistant.
2. **Broken favorites.** The radio stations behind the favorites come from vTuner via Libratone's service, and
   more and more of them no longer play: on a Zipp with the factory favorites, three of the five are dead. Some
   years ago Libratone had to ship a firmware update because all stations had stopped working; there's no
   guarantee that will happen again. The event fires also when a favorite fails, so a dead slot can be given a
   working stream.

The integration doesn't act on it. If nobody in the household relies on a slot in the app, an automation can
put any stream on that slot, e.g. a Radio Browser station that vTuner doesn't have:

```yaml
automation:
  - alias: "Zipp2: heart slot 1 plays my station"
    triggers:
      - trigger: state
        entity_id: event.zipp2_favorite_started
    conditions:
      - condition: template
        value_template: >
          {{ trigger.to_state.attributes.event_type == 'favorite_1'
             and trigger.to_state.attributes.started_by == 'speaker_or_app' }}
    actions:
      - action: media_player.play_media
        target:
          entity_id: media_player.zipp2
        data:
          media_content_id: "https://example.org/my-station.mp3"
          media_content_type: music
          extra:
            title: "My station"
```

## Sources

| Source | Status |
|---|---|
| Spotify Connect | tested: detected with title, artist, album, cover |
| Bluetooth | tested: detected while playing (shown as playing) |
| Radio favorites (vTuner) | tested: play by name, save the playing station |
| DLNA / media from Home Assistant (Radio Browser, local media, TTS) | tested |
| AirPlay | not tested yet |
| AUX in | not tested yet |
| USB | not tested yet (the app knows USB commands: 1536-1538 `fetchUsbCurrentPlayId` / `PlayMode` / `SongInfo`) |
| Tidal, Douban FM, Kaishu, Ximalaya, Baidu, Audiogum | reported by the speaker as supported services (cmd 281), not tested |

## Help wanted: other Libratone speakers

| Speaker | Status |
|---|---|
| Zipp (LTH300, firmware 879) | tested |
| Zipp Mini (1st gen) | everything that worked on the Zipp up to v4 works the same; v5 features not tested yet |
| Zipp 2 / Zipp Mini 2 | probably mostly works (extra features like Alexa won't be exposed) |
| Classic, Diva, Loop, Live, Lounge | unknown (WiFi models, maybe the same protocol) |
| ONE, TOO | Bluetooth only: not supported |

What to report (open an issue): the model shown on the device page (or `model=` from the speaker's AirPlay
mDNS record), which entities work, and the log with `custom_components.libratone_zipp: debug`.

## Development

Tests run against fake speakers on loopback addresses (no hardware needed):

```sh
pip install pytest-homeassistant-custom-component
pytest
```

## Acknowledgment

This work is based on the following:

* The first Libratone command list is [coming from this work from Benjamin Hanke](https://www.loxwiki.eu/display/LOX/Libratone+Zipp+WLan+Lautsprecher)
* Entity to use: [Media Player](https://developers.home-assistant.io/docs/core/entity/media-player)
* Example of [integrations](https://www.home-assistant.io/integrations/#media-player):
    * Simple: [Harman Kardon AVR integration](https://www.home-assistant.io/integrations/harman_kardon_avr/) which use [this module](https://github.com/Devqon/hkavr)
    * Simple: [Clementine Music Player integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/clementine/media_player.py) which use [this module]()
    * Async: [Frontier Silicon integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/frontier_silicon) with [this module](https://github.com/zhelev/python-afsapi/tree/master/afsapi)
    * Async with extended features: [Yamaha integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/yamaha/) with [this module](https://github.com/wuub/rxv)

## License

See LICENSE file.
