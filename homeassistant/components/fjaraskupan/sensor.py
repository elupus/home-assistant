"""Support for sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import EntryState
from .const import DOMAIN
from .device import Device, State

ORDERED_DIM_LEVEL = ["1", "2", "3"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    entrystate: EntryState = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            GreaseFilterSensor(entrystate.coordinator, entrystate.device),
            CarbonFilterSensor(entrystate.coordinator, entrystate.device),
        ]
    )


class Sensor(CoordinatorEntity[State], SensorEntity):
    """Sensor device."""

    def _update_from_device_state(self, data: State):
        pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        if data := self.coordinator.data:
            self._update_from_device_state(data)
        else:
            self._attr_state = None
        self.async_write_ha_state()


class GreaseFilterSensor(Sensor):
    """Grease filter sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[State], device: Device
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-grease-filter"
        self._attr_name = "Fjäråskupan Grease Filter"
        self._update_from_device_state(coordinator.data)

    def _update_from_device_data(self, data: State) -> None:
        self._attr_state = str(data.grease_filter_full)


class CarbonFilterSensor(Sensor):
    """Grease filter sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[State], device: Device
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-carbon-filter"
        self._attr_name = "Fjäråskupan Carbon Filter"
        self._update_from_device_state(coordinator.data)

    def _update_from_device_data(self, data: State) -> None:
        self._attr_state = str(data.carbon_filter_full)
