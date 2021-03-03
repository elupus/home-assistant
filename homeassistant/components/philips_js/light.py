"""Component to integrate ambilight for TVs exposing the Joint Space API."""
from typing import Any, Dict, Optional

from haphilipsjs.typing import AmbilightCurrentConfiguration

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import color_hsv_to_RGB, color_RGB_to_hsv

from . import PhilipsTVDataUpdateCoordinator
from .const import CONF_SYSTEM, DOMAIN

ACTIVE_MODES = ["manual", "expert", "lounge"]
EFFECT_PARTITION = ": "
EFFECT_MODE = "Mode"


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            PhilipsTVLightEntity(
                coordinator, config_entry.data[CONF_SYSTEM], config_entry.unique_id
            )
        ]
    )


def _get_settings(style: AmbilightCurrentConfiguration):
    """Extract the color settings data from a style."""
    if style["styleName"] in ("FOLLOW_COLOR", "Lounge light"):
        return style["colorSettings"]
    if style["styleName"] == "FOLLOW_AUDIO":
        return style["audioSettings"]
    return None


def _get_effect(style: str, algorithm: Optional[str]):
    """Return the effect string based on the style and algorithm."""
    if algorithm:
        return f"{style}{EFFECT_PARTITION}{algorithm}"
    return style


def _average_pixels(data):
    """Calculate an average color over all ambilight pixels."""
    color_c = 0
    color_r = 0.0
    color_g = 0.0
    color_b = 0.0
    for layer in data.values():
        for side in layer.values():
            for pixel in side.values():
                color_c += 1
                color_r += pixel["r"]
                color_g += pixel["g"]
                color_b += pixel["b"]

    if color_c:
        color_r /= color_c
        color_g /= color_c
        color_b /= color_c
        return color_r, color_g, color_b
    return 0.0, 0.0, 0.0


class PhilipsTVLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        system: Dict[str, Any],
        unique_id: str,
    ):
        """Initialize light."""
        self._tv = coordinator.api
        self._hsv = None
        self._system = system
        self._unique_id = unique_id
        self._coordinator = coordinator
        super().__init__(coordinator)

        self._update_from_coordinator()

    @property
    def name(self):
        """Return the device name."""
        return self._system["name"]

    @property
    def unique_id(self):
        """Return unique identifier if known."""
        return self._unique_id

    @property
    def supported_features(self):
        """Return supported features on this light."""
        return SUPPORT_EFFECT | SUPPORT_COLOR | SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """Device should be polled."""
        return False

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        effects = []

        effects.extend(
            _get_effect(style["styleName"], algo)
            for style in self._coordinator.api.ambilight_styles.values()
            for algo in style.get("algorithms", {})
        )

        effects.extend(
            _get_effect(EFFECT_MODE, mode)
            for mode in self._coordinator.api.ambilight_modes
            if mode in ACTIVE_MODES
        )

        return effects

    @property
    def effect(self):
        """Return the current effect."""
        current = self._coordinator.api.ambilight_current_configuration
        if current and current["isExpert"]:
            settings = _get_settings(current)
            if settings:
                return _get_effect(current["styleName"], settings["algorithm"])
            return _get_effect(current["styleName"], None)

        return _get_effect(EFFECT_MODE, self._coordinator.api.ambilight_mode)

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv:
            return self._hsv[:2]
        return None

    @property
    def brightness(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv:
            return self._hsv[2]
        return None

    @property
    def is_on(self):
        """Return if the light is turned on."""
        if not self._tv:
            return False

        current = self._coordinator.api.ambilight_current_configuration
        if current and current["isExpert"]:
            return True

        return (
            self._tv.ambilight_power == "On" and self._tv.ambilight_mode in ACTIVE_MODES
        )

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "name": self._system["name"],
            "identifiers": {
                (DOMAIN, self._system["serialnumber"]),
            },
            "model": self._system["model"],
            "manufacturer": "Philips",
            "sw_version": self._system["softwareversion"],
        }

    def _update_from_coordinator(self):
        current = self._tv.ambilight_current_configuration
        color = None
        if current and current["isExpert"]:
            settings = _get_settings(current)
            if settings:
                color = settings["color"]

        if color:
            self._hsv = (
                color["hue"] * 360.0 / 255.0,
                color["saturation"] * 100.0 / 255.0,
                color["brightness"],
            )
        else:
            data = self._tv.ambilight_cached
            if data:
                hsv_h, hsv_s, hsv_v = color_RGB_to_hsv(*_average_pixels(data))
                self._hsv = hsv_h, hsv_s, hsv_v * 255.0 / 100.0
            else:
                self._hsv = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    async def _set_ambilight_cached(self, algorithm, hs_color, brightness):
        """Set ambilight via the manual or expert mode."""
        rgb = color_hsv_to_RGB(hs_color[0], hs_color[1], brightness * 100 / 255)

        data = {
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
        }

        if not await self._tv.setAmbilightCached(data):
            raise Exception("Failed to set ambilight color")

        if algorithm == "internal":
            algo = "manual"

        if algo != self._tv.ambilight_mode:
            if not await self._tv.setAmbilightMode(algorithm):
                raise Exception("Failed to set ambilight mode")

    async def _set_ambilight_config(self, style, algorithm, hs_color, brightness):
        """Set ambilight via current configuration."""
        config: AmbilightCurrentConfiguration = {
            "styleName": style,
            "isExpert": True,
        }

        setting = {
            "algorithm": algorithm,
            "color": {
                "hue": round(hs_color[0] * 255.0 / 360.0),
                "saturation": round(hs_color[1] * 255.0 / 100.0),
                "brightness": round(brightness),
            },
            "colorDelta": {
                "hue": 0,
                "saturation": 0,
                "brightness": 0,
            },
        }

        if style in ("FOLLOW_COLOR", "Lounge light"):
            config["colorSettings"] = setting
            config["speed"] = 2

        elif style == "FOLLOW_AUDIO":
            config["audioSettings"] = setting
            config["tuning"] = 0

        if not await self._tv.setAmbilightCurrentConfiguration(config):
            raise Exception("Failed to set ambilight mode")

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        effect = kwargs.get(ATTR_EFFECT)

        if not self._tv.on:
            raise Exception("TV is not available")

        if self._tv.ambilight_power != "On":
            if not await self._tv.setAmbilightPower("On"):
                raise Exception("Failed to set ambilight power")

        if effect is None:
            effect = self.effect

        if brightness is None:
            if self.brightness:
                brightness = self.brightness
            else:
                brightness = 255

        if hs_color is None:
            if self.hs_color:
                hs_color = self.hs_color
            else:
                hs_color = [0, 0]

        style, _, algorithm = effect.partition(EFFECT_PARTITION)
        if style == EFFECT_MODE:
            await self._set_ambilight_cached(algorithm, hs_color, brightness)
        else:
            await self._set_ambilight_config(style, algorithm, hs_color, brightness)

        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn of ambilight."""

        if not self._tv.on:
            raise Exception("TV is not available")

        current = self._tv.ambilight_current_configuration
        if current and current["isExpert"]:
            config: AmbilightCurrentConfiguration = {
                "styleName": "FOLLOW_VIDEO",
                "isExpert": False,
                "menuSetting": "Standard",
            }
            if not await self._tv.setAmbilightCurrentConfiguration(config):
                raise Exception("Failed to set ambilight configuration")
        else:
            if not await self._tv.setAmbilightMode("internal"):
                raise Exception("Failed to set ambilight mode")

        self.async_write_ha_state()
