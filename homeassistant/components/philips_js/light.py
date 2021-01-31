"""Component to integrate ambilight for TVs exposing the Joint Space API."""
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

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([PhilipsTVLightEntity(coordinator)])


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

    def __init__(self, coordinator: PhilipsTVDataUpdateCoordinator):
        """Initialize light."""
        self._tv = coordinator.api
        self._hsv = None
        self._system = coordinator.system
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
        return self._system["serialnumber"]

    @property
    def supported_features(self):
        """Return supported features on this light."""
        return SUPPORT_EFFECT | SUPPORT_COLOR | SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return ["internal", "manual", "expert"]

    @property
    def effect(self):
        """Return the current effect."""
        return self._coordinator.ambilight_mode

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv:
            return self._hsv[:2]

    @property
    def brightness(self):
        """Return the hue and saturation color value [float, float]."""
        if self._hsv:
            return self._hsv[2] * 255 / 100

    @property
    def is_on(self):
        """Return if the light is turned on."""
        return self._tv.on

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
        if self._coordinator.ambilight_mode == "internal":
            data = self._coordinator.ambilight_processed
        else:
            data = self._coordinator.ambilight_cached

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

    def turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        effect = kwargs.get(ATTR_EFFECT)

        if not self._tv.on:
            raise Exception("Light is not turned on")

        if effect:
            if not self._tv.setAmbilightMode(effect):
                raise Exception("Failed to set ambilight mode")

        if brightness or hs_color:
            if brightness is None:
                brightness = self.brightness
            if hs_color is None:
                hs_color = self.hs_color
            if brightness is None or hs_color is None:
                raise Exception("Can't figure out color")

            rgb = color_hsv_to_RGB(hs_color[0], hs_color[1], brightness * 100 / 255)

            data = {
                "r": rgb[0],
                "g": rgb[1],
                "b": rgb[2],
            }
            if not self._tv.setAmbilightCached(data):
                raise Exception("Failed to set ambilight color")

        self.hass.add_job(self._coordinator.async_request_refresh)
