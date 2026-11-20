from homeassistant.const import Platform

DOMAIN = "libratone_zipp"
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

CONF_SERIAL = "serial"
MANUFACTURER = "Libratone"
