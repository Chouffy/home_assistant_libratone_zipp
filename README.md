# Libratone Zipp controller for Home Assistant

This controls Libratone Zipp speakers from [Home Assistant](https://www.home-assistant.io/).

Since v5 the protocol code lives inside the integration (`custom_components/libratone_zipp/{protocol,speaker,hub}.py`, asyncio, no external dependency).
Speakers are identified by **serial number**, not IP: when a speaker comes back from sleep/power-off with a new DHCP address, the integration finds it again by itself (zeroconf, plus a small UDP sweep of the subnet while a speaker is missing).

## Limitations / Known bugs

* Group (SoundSpace Link) state is only pushed by the speakers when it changes. After a Home Assistant restart the last known group is restored, but a change made while HA was down is only seen at the next group change.
* Mute can be read but not set (command unknown).
* Playing arbitrary media (`play_media`) is not supported; the five favorites are available as sources.

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


Other functionalities - Not planned right now:

* Module
    * [ ] Make the module async
    * [ ] Submit it for official integration!
    * [ ] Add support for other libratone speakers
* Current Playback info
    * [ ] Retrieve current playback source
    * [ ] Retrieve media type: bluetooth, spotify, aux, radio, ...
* Standby
    * [ ] Set a standby timer
    * [ ] Retrieve a standby timer
* Voicing & Room Setting
    * [ ] Set Room Setting
    * [ ] Retrieve current Room Setting
* Favorites
    * [ ] Play a favorite (proper title)
    * [ ] Set a Favorite
* Extended current playback info
    * [ ] Set extended playback status: shuffle, repeat
    * [ ] Retrieve extended playback status: shuffle, repeat
    * [ ] Set Source
    * [ ] Retrieve current source
* Multi-room
    * [ ] Set speaker mode (stereo, left, right)
    * [ ] Add better media player cards

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
