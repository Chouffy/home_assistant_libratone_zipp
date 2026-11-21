"""Battery sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LibratoneConfigEntry
from .const import COLORS
from .entity import LibratoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LibratoneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    spk = entry.runtime_data
    async_add_entities([
        BatterySensor(entry, spk),
        ColorSensor(entry, spk),
        WifiSignalSensor(entry, spk),
        TextDiagnostic(entry, spk, "wifi_network", "mdi:wifi", lambda s: s.ssid),
        TextDiagnostic(entry, spk, "ip_address", "mdi:ip-network", lambda s: s.host or None),
    ])


class BatterySensor(LibratoneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_battery"

    @property
    def native_value(self) -> int | None:
        return self.speaker.battery


class ColorSensor(LibratoneEntity, SensorEntity):
    """The speaker's color as stored on the speaker (the app shows it). Helps telling speakers apart."""

    _attr_translation_key = "color"
    _attr_icon = "mdi:palette"

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_color"

    @property
    def native_value(self) -> str | None:
        code = self.speaker.color
        return COLORS.get(code, f"Code {code}") if code else None

    @property
    def extra_state_attributes(self) -> dict:
        return {"color_code": self.speaker.color}


class WifiSignalSensor(LibratoneEntity, SensorEntity):
    """WiFi signal in % (the speaker reports 0-5 bars)."""

    _attr_translation_key = "wifi_signal"
    _attr_icon = "mdi:wifi"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, speaker) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_wifi_signal"

    @property
    def native_value(self) -> int | None:
        bars = self.speaker.wifi_bars
        return None if bars is None else bars * 20

    @property
    def extra_state_attributes(self) -> dict:
        return {"raw": self.speaker.signal}


class TextDiagnostic(LibratoneEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, speaker, key: str, icon: str, getter) -> None:
        super().__init__(entry, speaker)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_icon = icon
        self._getter = getter

    @property
    def native_value(self) -> str | None:
        return self._getter(self.speaker)
