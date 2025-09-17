import logging
import voluptuous as vol

# Prefer vendored lib during dev. Fall back to PyPI if not present
try:
    from .vendor.python_libratone_zipp.python_libratone_zipp import LibratoneZipp  # type: ignore
except Exception:  # pragma: no cover
    from python_libratone_zipp import LibratoneZipp  # type: ignore

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from homeassistant.const import CONF_NAME


from homeassistant.components.media_player.const import (
    MediaType,
    MediaPlayerEntityFeature,
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
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger("LibratoneZippDevice")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from a config entry."""
    zipp_client = hass.data[DOMAIN][entry.entry_id]
    name = entry.title or entry.data.get(CONF_NAME) or DEFAULT_NAME
    async_add_entities([LibratoneZippDevice(zipp_client, name)])

def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up Libratone Zipp"""

    host = config[CONF_HOST]
    name = config[CONF_NAME]
    #_LOGGER.warning(f"setup_platform called for host={host}, name={name}")

    zipp_client = LibratoneZipp(host)

    # Bootstrap a bit of state so attributes aren't None on first render
    try:
        zipp_client.name_get()
        zipp_client.version_get()
        zipp_client.volume_get()
    except Exception:
        _LOGGER.debug("Initial bootstrap calls failed; will rely on polling.")

    # Ensure cleanly stop threads/sockets on HA shutdown
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
    def _on_stop(_):
        try:
            zipp_client.exit()
        except Exception:
            pass
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)

    add_entities([LibratoneZippDevice(zipp_client, name)])

class LibratoneZippDevice(MediaPlayerEntity):
    """Representation of a Libratone Zipp speaker."""

    def __init__(self, zipp_client, name):
        """Initialize a new Libratone Zipp device"""
        self.zipp = zipp_client
        self._name = name

        self._device_type = DEVICE_CLASS_SPEAKER

        self._state = None
        self._volume_level = None

        self._sound_mode = None
        self._sound_mode_list = None

        self._track_name = None
        self._track_artist = None

        # self._source = None
        self._source_list = ["1", "2", "3", "4", "5"]

        self.update()

    def update(self):
        """Update the state of this media_player."""

        if self.zipp.name != None:
            self._name = self.zipp.name
        self._sound_mode_list = self.zipp.voicing_list
        self._sound_mode = self.zipp.voicing

        self._track_name = self.zipp.play_title
        self._track_artist = self.zipp.play_subtitle

        # Update of state
        if self.zipp.state == "SLEEPING":
            self._state = STATE_OFF
        elif self.zipp.state == "PLAYING":
            self._state = STATE_PLAYING
        elif self.zipp.state == "PAUSED":
            self._state = STATE_PAUSED
        elif self.zipp.state == "STOPPED" or self.zipp.state == "ON":
            self._state = STATE_IDLE
        else:
            self._state = STATE_UNKNOWN

        # Update of volume
        if self.zipp.volume != None:
            self._volume_level = int(self.zipp.volume) / 100

    @property
    def unique_id(self):
        """Stable id for registry."""
        serial = getattr(self.zipp, "serialnumber", None)
        host_tag = str(self.zipp.host).replace(".", "_")
        if serial:
            return f"libratone_{serial}_{host_tag}"
        return f"libratone_{host_tag}"

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
        return MediaType.MUSIC

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

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_name

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._track_artist

    def turn_on(self):
        """Turn the media player on."""
        return self.zipp.wakeup()

    def turn_off(self):
        """Turn the media player off."""
        return self.zipp.sleep()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        # In order to get a smooth volume slider, volume is overriden here - but it will be updated later anyway
        self._volume_level = volume
        return self.zipp.volume_set(int(volume * 100))

    def media_play(self):
        """Send play command."""
        return self.zipp.play()

    def media_pause(self):
        """Send pause command."""
        return self.zipp.pause()

    def media_stop(self):
        """Send stop command."""
        return self.zipp.stop()

    def media_next_track(self):
        """Send next command."""
        return self.zipp.next()

    def media_previous_track(self):
        """Send prev command."""
        return self.zipp.prev()

    def select_source(self, source):
        """Select input source."""
        return self.zipp.favorite_play(source)

    def select_sound_mode(self, sound_mode):
        """ "Select sound mode."""
        return self.zipp.voicing_set(sound_mode)
