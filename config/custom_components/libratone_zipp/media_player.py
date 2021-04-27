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
    SUPPORT_SELECT_SOUND_MODE,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_IDLE,
    STATE_ON,
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

    zipp = LibratoneZipp(host, name)
    zipp_device = LibratoneZippDevice(zipp)

    add_entities([zipp_device], True)


class LibratoneZippDevice(MediaPlayerEntity):
    """Representation of a Libratone Zipp speaker."""

    def __init__(self, zipp):
        """Initialize a new Libratone Zipp device"""
        self._zipp = zipp

        self._name = zipp.name
        self._host = zipp.host

        self._sound_mode = None
        self._sound_mode_list = zipp.voicing_list

        self._state = STATE_ON
        self._device_type = DEVICE_CLASS_SPEAKER

    def update(self):
        """Update the state of this media_player."""
        self._sound_mode = self._zipp.voicing

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_LIBRATONE_ZIPP

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return the current sound mode."""
        return self._sound_mode_list

    def media_play(self):
        """Send play command."""
        self._state = STATE_PLAYING
        return self._zipp.play()

    def media_pause(self):
        """Send pause command."""
        self._state = STATE_PAUSED
        return self._zipp.pause()

    def media_stop(self):
        """Send stop command."""
        self._state = STATE_IDLE
        return self._zipp.stop()

    def media_next_track(self):
        """Send next command."""
        self._state = STATE_PLAYING
        return self._zipp.next()

    def media_previous_track(self):
        """Send prev command."""
        self._state = STATE_PLAYING
        return self._zipp.prev()

    def select_sound_mode(self, sound_mode):
        """Set Sound Mode for Receiver.."""
        self._zipp.voicing_set(sound_mode)
        self._sound_mode = sound_mode
        return True
        