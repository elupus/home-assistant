"""Philips TV menu switches."""

from __future__ import annotations

from typing import Any

from haphilipsjs.typing import (
    MenuItemsSettingsUpdateValueData,
    MenuItemsSettingsValueBool,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PhilipsTVConfigEntry, PhilipsTVDataUpdateCoordinator
from .entity import PhilipsJsEntity, PhilipsTVSettingsEntity

HUE_POWER_OFF = "Off"
HUE_POWER_ON = "On"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PhilipsTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = config_entry.runtime_data

    entities: list[SwitchEntity] = []
    entities.append(PhilipsTVScreenSwitch(coordinator))
    entities.extend(
        PhilipsTVMenuSwitch(coordinator, data["node"], data["name"])
        for data in coordinator.settings_nodes
        if data["node"]["type"] == "TOGGLE_NODE"
    )

    async_add_entities(entities)

    if coordinator.api.json_feature_supported("ambilight", "Hue"):
        async_add_entities([PhilipsTVAmbilightHueSwitch(coordinator)])


class PhilipsTVScreenSwitch(PhilipsJsEntity, SwitchEntity):
    """A Philips TV screen state switch."""

    _attr_translation_key = "screen_state"

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_screenstate"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate == "On"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.screenstate == "On"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setScreenState("On")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setScreenState("Off")


class PhilipsTVAmbilightHueSwitch(PhilipsJsEntity, SwitchEntity):
    """A Philips TV Ambi+Hue switch."""

    _attr_translation_key = "ambilight_hue"

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_ambi_hue"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate == "On"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.huelamp_power == HUE_POWER_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setHueLampPower(HUE_POWER_ON)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setHueLampPower(HUE_POWER_OFF)
        self.async_write_ha_state()


class PhilipsTVMenuSwitch(PhilipsTVSettingsEntity, SwitchEntity):
    """A Philips TV menu settings switch."""

    _data: MenuItemsSettingsValueBool | None

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if not self._data:
            return False

        return self._data["value"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off(False)

    async def _async_turn_on_off(self, value: bool) -> None:
        """Change the selected option."""
        data: dict[int, MenuItemsSettingsUpdateValueData] = {
            self._node["node_id"]: {"value": value}
        }
        await self.coordinator.api.postMenuItemsSettingsUpdateData(data)
        await self.coordinator.async_request_refresh()
