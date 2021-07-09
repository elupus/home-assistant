"""Support for sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import EntryState
from .const import DOMAIN
from .device import Device, State


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    entrystate: EntryState = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            GreaseFilterSensor(
                entrystate.coordinator, entrystate.device, entrystate.device_info
            ),
            CarbonFilterSensor(
                entrystate.coordinator, entrystate.device, entrystate.device_info
            ),
        ]
    )


class Sensor(CoordinatorEntity[State], BinarySensorEntity):
    """Sensor device."""

    def _update_from_device_state(self, data: State):
        pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._update_from_device_state(self.coordinator.data)
        self.async_write_ha_state()


class GreaseFilterSensor(Sensor):
    """Grease filter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-grease-filter"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} Grease Filter"
        self._attr_device_class = DEVICE_CLASS_PROBLEM
        self._update_from_device_state(coordinator.data)

    def _update_from_device_data(self, data: State) -> None:
        if data:
            self._attr_is_on = data.grease_filter_full
        else:
            self._attr_is_on = None


class CarbonFilterSensor(Sensor):
    """Grease filter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-carbon-filter"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} Carbon Filter"
        self._attr_device_class = DEVICE_CLASS_PROBLEM
        self._update_from_device_state(coordinator.data)

    def _update_from_device_data(self, data: State) -> None:
        if data:
            self._attr_is_on = data.carbon_filter_full
        else:
            self._attr_is_on = None
