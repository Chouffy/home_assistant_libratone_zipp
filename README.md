# Libratone Zipp controller for Home Assistant

This aims to control a Libratone Zipp speaker within [Home Assistant](https://www.home-assistant.io/) using [this Python library](https://github.com/Chouffy/python_libratone_zipp).

Pre-requisites: the [python-libratone-zipp](https://pypi.org/project/python-libratone-zipp/) library.

## Usage

Currently, this module has to be installed manually:

1. Copy `/config/*` in your `/config/` directory of Home Assistant.
1. Add the following in your `/config/configuration.yaml`

    ```yaml
    media_player:
      - platform: libratone_zipp
        host: 192.168.99.99
        name: "Zipp"
    ```

1. Restart the server

## Roadmap

* [x] Set up entity in home assistant
* [x] Basic playback status
* [x] Calculate status
* [x] Set a sound mode (voicing)
* [ ] Retrieve basic playback status: play, pause, stop, next, prev
* [ ] Make the module async

Other functionalities:

* Volume
    * [ ] Set volume
    * [ ] Retrieve volume
* Current Playback info
    * [ ] Retrieve current playback source
    * [ ] Retrieve current title
    * [ ] Retrieve media type: bluetooth, spotify, aux, radio, ...
* Standby
    * [ ] Set to immediate standby
    * [ ] Set a standby timer
    * [ ] Retrive a standby timer
* Voicing & Room Setting
    * [ ] Retrieve current Voicing
    * [ ] Set Room Setting
    * [ ] Retrieve current Room Setting
* Favorites
    * [ ] Play a favorite
    * [ ] Set a Favorite
* Extended current playback info
    * [ ] Set extended playback status: shuffle, repeat
    * [ ] Retrieve extended playback status: shuffle, repeat
    * [ ] Set Source
    * [ ] Retrieve current source

## Acknowledgment

This work is based on the following:

* The Libratone command list is [coming from this work from Benjamin Hanke](https://www.loxwiki.eu/display/LOX/Libratone+Zipp+WLan+Lautsprecher)
* Entity to use: [Media Player](https://developers.home-assistant.io/docs/core/entity/media-player)
* Example of [integrations](https://www.home-assistant.io/integrations/#media-player):
    * Simple: [Harman Kardon AVR integration](https://www.home-assistant.io/integrations/harman_kardon_avr/) which use [this module](https://github.com/Devqon/hkavr)
    * Simple: [Clementine Music Player integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/clementine/media_player.py) which use [this module]()
    * Async: [Frontier Silicon integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/frontier_silicon) with [this module](https://github.com/zhelev/python-afsapi/tree/master/afsapi)
    * Async with extended features: [Yamaha integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/yamaha/) with [this module](https://github.com/wuub/rxv)
