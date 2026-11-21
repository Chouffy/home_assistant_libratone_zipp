# Libratone Zipp controller for Home Assistant

This controls Libratone Zipp speakers from [Home Assistant](https://www.home-assistant.io/).

Since v5 the protocol code lives inside the integration (`custom_components/libratone_zipp/{protocol,speaker,hub}.py`, asyncio, no external dependency).
Speakers are identified by **serial number**, not IP: when a speaker comes back from sleep/power-off with a new DHCP address, the integration finds it again by itself (zeroconf, plus a small UDP sweep of the subnet while a speaker is missing).

## Limitations / Known bugs

* Sources can't be switched from Home Assistant except the five favorites (the app can't either: Spotify is
  controlled via Spotify Connect, Bluetooth from the phone). They are detected though: Spotify, Bluetooth, favorites.
* Bluetooth: playback is detected (shown as playing, source "Bluetooth"), whether a phone is *connected* is not.
  Bluetooth has its own volume, which the speaker doesn't report.
* Mute can be read but not set (command unknown).
* Playing arbitrary media (`play_media`) is not supported.

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
    * [x] Async, built-in protocol code (no PyPI dependency)
    * [x] Speakers tracked by serial number; automatic recovery after IP changes, proper `unavailable` state
    * [x] Push updates instead of 5 s polling
    * [x] Artist, album, playlist, cover art, current source (Spotify, favorite name, ...)
    * [x] Favorites by name, room placement select, battery sensor, device entries
    * [x] Group members master-first, slave mirrors the master's media, app-compatible link ids
    * [x] Group state polled from the speakers' LSSDP status (UDP 1800): correct right after an HA restart
    * [x] Audio channel select (stereo / left / right)
    * [x] Source detection incl. Bluetooth; Bluetooth playback shows as playing (was: only "Play" button)


Roadmap (status after v5, 2026-11-20):

* Module
    * [x] Make the module async
    * [ ] Submit it for official integration!
    * [ ] Add support for other libratone speakers (only Zipp LTH300, firmware 879 tested)
* Current Playback info
    * [x] Retrieve current playback source
    * [x] Retrieve media type: bluetooth, spotify, radio (aux untested)
* Standby
    * [x] Set a standby (sleep) timer: `number.<speaker>_sleep_timer`, minutes, 0 = off
    * [x] Retrieve a standby timer (shows the remaining time, counts down)
    * [ ] Auto-standby time (cmd 528 reads `300`; the app has no setting for it)
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
    * [ ] Add better media player cards
* One player instead of two (Libratone + DLNA)
    * [x] Register the speaker's MAC (LSSDP `DeviceID`) as device connection (note: current HA versions no longer merge devices across integrations)
    * [x] `play_media` + media browser via the speaker's own UPnP renderer (AVTransport on :49152, `async-upnp-client`):
          local media, Radio Browser, TTS. The separate DLNA entity isn't needed any more
* Other models
    * [x] Model from the speaker's UPnP description (`LTH300` -> Zipp) instead of a fixed "Zipp"
    * [ ] Test Zipp Mini / Zipp 2 / Zipp Mini 2 (one capture or a test run with each is enough)
* Colors and names
    * [x] Read and set the color (`select.<speaker>_color`, all 15 colors mapped, SET 771 verified), with a color swatch
    * [x] Picture: the media player shows a drawn Zipp in the speaker's color when there's no cover (no Libratone images shipped)
    * [x] Rename the speaker (`text.<speaker>_speaker_name`, SET 90, verified)
* Network and diagnostics
    * [x] WiFi signal, WiFi network, IP address as diagnostic sensors; firmware, MAC and a link to the speaker's web UI on the device page
    * [ ] Bluetooth: connection state / pairing (not visible on the network side so far)
* Setup without the app (in case Libratone's app/servers go away)
    * [ ] WiFi setup through the speaker's own web UI (`cgi?Network` -> `cgi?SetNet`), incl. a factory-new speaker's setup hotspot (needs a capture)
    * [ ] Factory reset (SET 150, known; not exposed on purpose yet)
* Radio
    * [x] Favorites: play by name, save the playing station (`select.<speaker>_save_playing_station_as_favorite` or `libratone_zipp.save_favorite`)
    * [ ] Save Spotify content as a favorite (the app can; needs a capture)
    * [x] Any station: via `play_media` / media browser (e.g. Radio Browser), independent of vTuner/Libratone

## Help wanted: other Libratone speakers

Tested: **Zipp** (LTH300, firmware 879). The first-generation **Zipp Mini** is known to work the same way.
If you own one of these, a short test would help a lot:

| Speaker | Expected |
|---|---|
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
