from homeassistant.const import Platform

DOMAIN = "libratone_zipp"
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TEXT,
]

CONF_SERIAL = "serial"
CONF_REDISCOVER = "rediscover"   # option: sweep the subnet for a speaker whose IP changed (off)
CONF_MAC = "mac"
MANUFACTURER = "Libratone"

# UPnP modelName + modelNumber -> product name. Only LTH300 is confirmed; please report others.
MODELS = {"LTH300": "Zipp"}

# Color codes (GET 770 / SET 771) -> (name as in the app, hex). Codes mapped on a Zipp by setting each color
# in the app and reading GET 770; hex from libratone.com's color swatches.
# 1xxx are the wool covers, 2xxx the mesh covers. Pepper Black, Salty Grey and Signal aren't on the website:
# their hex values are approximations.
COLORS: dict[str, tuple[str, str]] = {
    "1001": ("Pepper Black", "#232323"),     # approx.
    "1002": ("Salty Grey", "#c8c5be"),       # approx.
    "1003": ("Steel Blue", "#6b7681"),
    "1004": ("Raspberry Red", "#b41f2e"),
    "1005": ("Almond Brown", "#bd9d88"),
    "1006": ("Icy Blue", "#028cc1"),
    "2001": ("Cloudy Grey", "#b4b4b4"),
    "2002": ("Graphite Grey", "#4f4f4f"),
    "2003": ("Victory Red", "#d20720"),
    "2004": ("Deep Lagoon", "#05937a"),
    "2005": ("Sangria", "#aa0699"),
    "2006": ("Atlantic Deep", "#518296"),
    "2007": ("Signal", "#e8e337"),           # approx.
    "2008": ("Nude", "#deb69b"),
    "2009": ("Pastel Blue", "#bbdbe2"),
}
COLOR_CODES_BY_NAME = {name: code for code, (name, _hex) in COLORS.items()}
