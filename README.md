# Libratone Zipp controller for Home Assistant

This aims to control a Libratone Zipp speaker within [Home Assistant](https://www.home-assistant.io/) using [this Python library](https://github.com/Chouffy/python_libratone_zipp).

## Usage

### Installation via [HACS](https://hacs.xyz/)

1. Add this repository `https://github.com/Chouffy/home_assistant_libratone_zipp` as a custom repository with *integration* type
1. Click *Install*
1. Add the following in your `/config/configuration.yaml`:

    ```yaml
    media_player:
    - platform: libratone_zipp
        host: 192.168.XX.XX
        name: Zipp
        scan_interval: 2
    ```

    * Only one speaker is supported!
    * I suggest `scan_interval: 2` to get 2 seconds refresh rate

1. Restart the server
1. You need to forward `3333/udp` and `7778/udp` if you're using Docker/devcontainer

## Features

### Known bugs

* Major:
    * Only one speaker is supported - this needs this [upstream module issue](https://github.com/Chouffy/python_libratone_zipp/issues/1) to be fixed
    * On Bluetooth and when the music is playing, you only get "Play" button, not Pause.
* Minor:
    * After a restart of Home Assistant, the integration can be in an "unknown" state before the 1st music is played

### Functionnality coverage

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

Other functionalities:

* Module
    * [ ] Re-enable automatic HACS workflow
    * [ ] Submit it for non-official integration on HACS - in progress
    * [ ] Submit it for official integration!
    * [ ] Make the module async
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
    * [ ] Implement SoundSpace Link

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
