"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nibe.coil import Coil

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_HEAT_PUMP,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            WaterHeater(
                coordinator,
                "HW1",
                "Hot Water",
                current_address=40014,
                hot_water_production_address=47387,
                hot_water_comfort_mode_address=47041,
                start_temperature_address={
                    "ECONOMY": 47045,
                    "NORMAL": 47044,
                    "LUXURY": 47043,
                },
                stop_temperature_address={
                    "ECONOMY": 47049,
                    "NORMAL": 47048,
                    "LUXURY": 47047,
                },
                prio_address=43086,
                active_accessory_address=None,
            ),
        ]
    )


class WaterHeaterEntityFixed(WaterHeaterEntity):
    """Base class to disentangle the configuration of operation mode from the state."""

    _attr_operation_mode: str | None

    @property
    def operation_mode(self) -> str | None:
        """Return the operation modes currently configured."""
        if hasattr(self, "_attr_operation_mode"):
            return self._attr_operation_mode
        return self.current_operation

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        data = {}
        supported_features = self.supported_features or 0
        if supported_features & WaterHeaterEntityFeature.OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self._attr_operation_mode
        return data


class WaterHeater(CoordinatorEntity[Coordinator], WaterHeaterEntityFixed):
    """Sensor entity."""

    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: Coordinator,
        unique_id: str,
        name: str,
        current_address: int,
        hot_water_comfort_mode_address: int,
        hot_water_production_address: int,
        start_temperature_address: dict[str, int],
        stop_temperature_address: dict[str, int],
        prio_address: int,
        active_accessory_address: int | None,
    ) -> None:
        """Initialize entity."""

        super().__init__(
            coordinator,
            {
                current_address,
                hot_water_comfort_mode_address,
                hot_water_production_address,
                *set(start_temperature_address.values()),
                *set(stop_temperature_address.values()),
                prio_address,
                active_accessory_address,
            },
        )
        self._attr_entity_registry_enabled_default = active_accessory_address is None
        self._attr_available = False
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.unique_id}-{unique_id}"
        self._attr_device_info = coordinator.device_info

        self._attr_current_operation = None
        self._attr_operation_mode = None
        self._attr_operation_list = list(start_temperature_address.keys())
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_step = 0.5

        self._attr_max_temp = 35.0
        self._attr_min_temp = 5.0

        def _get(address: int) -> Coil:
            return coordinator.heatpump.get_coil_by_address(address)

        self._coil_current = _get(current_address)
        self._coil_start_temperature = {
            key: _get(address) for key, address in start_temperature_address.items()
        }
        self._coil_stop_temperature = {
            key: _get(address) for key, address in stop_temperature_address.items()
        }
        self._coil_prio = _get(prio_address)
        if active_accessory_address:
            self._coil_active_accessory = _get(active_accessory_address)
        else:
            self._coil_active_accessory = None

        self._coil_hot_water_production = _get(hot_water_production_address)

        self._coil_hot_water_comfort_mode = _get(hot_water_comfort_mode_address)
        if self._coil_hot_water_comfort_mode:
            self._attr_operation_list = list(
                self._coil_hot_water_comfort_mode.mappings.values()
            )
        else:
            self._attr_operation_list = None

        if self._coil_current:
            self._attr_temperature_unit = self._coil_current.unit

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        self._attr_current_temperature = self.coordinator.get_coil_float(
            self._coil_current
        )

        if hot_water_comfort_mode := self.coordinator.get_coil_value(
            self._coil_hot_water_comfort_mode
        ):
            self._attr_operation_mode = str(hot_water_comfort_mode)
            self._attr_target_temperature_low = self.coordinator.get_coil_float(
                self._coil_start_temperature.get(self._attr_operation_mode, None)
            )
            self._attr_target_temperature_high = self.coordinator.get_coil_float(
                self._coil_stop_temperature.get(self._attr_operation_mode, None)
            )
        else:
            self._attr_operation_mode = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None

        if (
            hot_water_production := self.coordinator.get_coil_value(
                self._coil_hot_water_production
            )
        ) and (prio := self.coordinator.get_coil_value(self._coil_prio)):
            if hot_water_production == "ON":
                if prio == "HOT WATER":
                    self._attr_current_operation = STATE_HEAT_PUMP
                else:
                    self._attr_current_operation = STATE_OFF
            else:
                self._attr_current_operation = STATE_OFF
        else:
            self._attr_current_operation = None

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self._coil_active_accessory:
            return True

        if active_accessory := self.coordinator.get_coil_value(
            self._coil_active_accessory
        ):
            return active_accessory == "ON"

        return False

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self.coordinator.async_write_coil(
            self._coil_hot_water_comfort_mode, operation_mode
        )
