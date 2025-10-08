# Libratone Zipp controller for Home Assistant

This aims to control a Libratone Zipp speaker within [Home Assistant](https://www.home-assistant.io/) using [this Python library](https://github.com/Chouffy/python_libratone_zipp).

## Limitations / Known bugs

* Major:
    * On Bluetooth and when the music is playing, you only get "Play" button, not Pause.
* Minor:
    * After a restart of Home Assistant, the integration can be in an "unknown" state before the 1st music is played

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
