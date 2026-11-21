from homeassistant.const import Platform

DOMAIN = "libratone_zipp"
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.TEXT]

CONF_SERIAL = "serial"
MANUFACTURER = "Libratone"

# UPnP modelName + modelNumber -> product name. Only LTH300 is confirmed; please report others.
MODELS = {"LTH300": "Zipp"}

# Color codes (cmd 770 / LSSDP ColorCode) -> name as in the app. 2002 confirmed on two Zipps,
# 1001/2005 from the original library. Map more with libratone-sniffing/weekend/color_map.py.
COLORS = {"1001": "Pepper Black", "2002": "Graphite Grey", "2005": "Sangria"}
