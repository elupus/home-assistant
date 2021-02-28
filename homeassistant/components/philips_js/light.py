"""Component to integrate ambilight for TVs exposing the Joint Space API."""
from typing import Any, Dict

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
from homeassistant.components.philips_js import PhilipsTVDataUpdateCoordinator
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import color_hsv_to_RGB, color_RGB_to_hsv

from .const import CONF_SYSTEM, DOMAIN

CONTROLLED_MODES = ["manual", "cached"]


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


def _average_pixels(data):
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
        return self._coordinator.api.ambilight_modes

    @property
    def effect(self):
        """Return the current effect."""
        return self._coordinator.api.ambilight_mode

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv and self._tv.ambilight_mode in CONTROLLED_MODES:
            return self._hsv[:2]

    @property
    def brightness(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv and self._tv.ambilight_mode in CONTROLLED_MODES:
            return self._hsv[2] * 255 / 100

    @property
    def is_on(self):
        """Return if the light is turned on."""
        return self._tv.on and self._tv.ambilight_power == "On"

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
        data = self._tv.ambilight_cached
        if data:
            color_r, color_g, color_b = _average_pixels(data)
            self._hsv = color_RGB_to_hsv(color_r, color_g, color_b)
        else:
            self._hsv = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        effect = kwargs.get(ATTR_EFFECT)

        if not self._tv.on:
            raise Exception("Light is not turned on")

        if self._tv.ambilight_power != "On":
            if not await self._tv.setAmbilightPower("On"):
                raise Exception("Failed to set ambilight power")

        if brightness or hs_color:
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

            hsv = [hs_color[0], hs_color[1], brightness * 100 / 255]

            rgb = color_hsv_to_RGB(*hsv)

            data = {
                "r": rgb[0],
                "g": rgb[1],
                "b": rgb[2],
            }
            if not await self._tv.setAmbilightCached(data):
                raise Exception("Failed to set ambilight color")

            if self._tv.ambilight_mode not in CONTROLLED_MODES and effect is None:
                effect = "manual"

        if effect and effect != self._tv.ambilight_mode:
            if not await self._tv.setAmbilightMode(effect):
                raise Exception("Failed to set ambilight mode")

        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn of ambilight."""

        if not self._tv.on:
            raise Exception("Light is not turned on")

        if not await self._tv.setAmbilightPower("Off"):
            raise Exception("Failed to set ambilight power")

        self.async_write_ha_state()
