import logging
from python_libratone_zipp import LibratoneZipp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_PLAY,
    SUPPORT_PAUSE,
    SUPPORT_STOP,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
    STATE_PAUSED,
    STATE_IDLE,
    STATE_UNKNOWN,
)

import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Libratone Zipp"
DEVICE_CLASS_SPEAKER = "speaker"

SUPPORT_LIBRATONE_ZIPP = (
    SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_STOP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger("LibratoneZippDevice")


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up Libratone Zipp"""

    host = config[CONF_HOST]
    name = config[CONF_NAME]

    zipp_client = LibratoneZipp(host, name)

    add_entities([LibratoneZippDevice(zipp_client)])


class LibratoneZippDevice(MediaPlayerEntity):
    """Representation of a Libratone Zipp speaker."""

    def __init__(self, zipp_client):
        """Initialize a new Libratone Zipp device"""
        self._zipp_client = zipp_client

        self._name = self._zipp_client.name
        self._host = self._zipp_client.host

        self._device_type = DEVICE_CLASS_SPEAKER

        self._state = None
        self._volume_level = None

        # self._source = None
        self._source_list = ["1", "2", "3", "4", "5"]

        self._sound_mode = None
        self._sound_mode_list = self._zipp_client.voicing_list

        self.update()

    def update(self):
        """Update the state of this media_player."""

        # Update of state
        if self._zipp_client.state == "OFF":
            self._state = STATE_OFF
        elif self._zipp_client.state == "PLAY":
            self._state = STATE_PLAYING
        elif self._zipp_client.state == "PAUSE":
            self._state = STATE_PAUSED
        elif self._zipp_client.state == "STOP":
            self._state = STATE_IDLE
        else:
            self._state = STATE_UNKNOWN

        # Update of volume
        if self._zipp_client.volume != None and self._zipp_client.volume != "":
            self._volume_level = int(self._zipp_client.volume) / 100

        # Update of sound mode
        self._sound_mode = self._zipp_client.voicing

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume_level

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_LIBRATONE_ZIPP

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    '''
    @property
    def source(self):
        """Name of the current input source."""
        return None
    '''

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return the current sound mode."""
        return self._sound_mode_list

    def turn_on(self):
        """Turn the media player on."""
        return self._zipp_client.wakeup()

    def turn_off(self):
        """Turn the media player off."""
        return self._zipp_client.sleep()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        # In order to get a smooth volume slider, volume is overriden here - but it will be updated later anyway
        self._volume_level = volume
        return self._zipp_client.volume_set(int(volume * 100))

    def media_play(self):
        """Send play command."""
        return self._zipp_client.play()

    def media_pause(self):
        """Send pause command."""
        return self._zipp_client.pause()

    def media_stop(self):
        """Send stop command."""
        return self._zipp_client.stop()

    def media_next_track(self):
        """Send next command."""
        return self._zipp_client.next()

    def media_previous_track(self):
        """Send prev command."""
        return self._zipp_client.prev()

    def select_source(self, source):
        """Select input source."""
        return self._zipp_client.favorite_play(source)

    def select_sound_mode(self, sound_mode):
        """ "Select sound mode."""
        return self._zipp_client.voicing_set(sound_mode)
