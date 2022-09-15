"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from nibe.coil import Coil

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
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
            Climate(
                coordinator,
                "S1",
                "Climate System S1",
                current_address=40033,
                setpoint_heat_address=47398,
                setpoint_cool_address=48785,
                prio_address=43086,
                mixing_valve_state_address=43096,
                active_accessory_address=None,
                use_room_sensor_address=47394,
                cooling_with_room_sensor_address=47340,
            ),
            Climate(
                coordinator,
                "S2",
                "Climate System S2",
                current_address=40032,
                setpoint_heat_address=47397,
                setpoint_cool_address=48784,
                prio_address=43086,
                mixing_valve_state_address=43095,
                active_accessory_address=47302,
                use_room_sensor_address=47393,
                cooling_with_room_sensor_address=47340,
            ),
            Climate(
                coordinator,
                "S3",
                "Climate System S3",
                current_address=40031,
                setpoint_heat_address=47396,
                setpoint_cool_address=48783,
                prio_address=43086,
                mixing_valve_state_address=43094,
                active_accessory_address=47303,
                use_room_sensor_address=47392,
                cooling_with_room_sensor_address=47340,
            ),
            Climate(
                coordinator,
                "S4",
                "Climate System S4",
                current_address=40030,
                setpoint_heat_address=47395,
                setpoint_cool_address=48782,
                prio_address=43086,
                mixing_valve_state_address=43093,
                active_accessory_address=47304,
                use_room_sensor_address=47391,
                cooling_with_room_sensor_address=47340,
            ),
        ]
    )


class Climate(CoordinatorEntity[Coordinator], ClimateEntity):
    """Sensor entity."""

    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: Coordinator,
        unique_id: str,
        name: str,
        current_address: int,
        setpoint_heat_address: int,
        setpoint_cool_address: int,
        prio_address: int,
        mixing_valve_state_address: int,
        active_accessory_address: int | None,
        use_room_sensor_address: int,
        cooling_with_room_sensor_address: int,
    ) -> None:
        """Initialize entity."""
        super().__init__(
            coordinator,
            {
                current_address,
                setpoint_heat_address,
                setpoint_cool_address,
                prio_address,
                mixing_valve_state_address,
                active_accessory_address,
                use_room_sensor_address,
                cooling_with_room_sensor_address,
            },
        )
        self._attr_available = False
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.unique_id}-{unique_id}"
        self._attr_device_info = coordinator.device_info
        self._attr_hvac_action = HVACAction.IDLE
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF, HVACMode.HEAT]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_step = 0.5
        self._attr_entity_registry_enabled_default = active_accessory_address is None

        self._attr_max_temp = 35.0
        self._attr_min_temp = 5.0

        def _get(address: int) -> Coil:
            return coordinator.heatpump.get_coil_by_address(address)

        self._coil_current = _get(current_address)
        self._coil_setpoint_heat = _get(setpoint_heat_address)
        self._coil_setpoint_cool = _get(setpoint_cool_address)
        self._coil_prio = _get(prio_address)
        self._coil_mixing_valve_state = _get(mixing_valve_state_address)
        if active_accessory_address is None:
            self._coil_active_accessory_address = None
        else:
            self._coil_active_accessory_address = _get(active_accessory_address)
        self._coil_use_room_sensor = _get(use_room_sensor_address)
        self._coil_cooling_with_room_sensor = _get(cooling_with_room_sensor_address)

        if self._coil_current:
            self._attr_temperature_unit = self._coil_current.unit

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        self._attr_current_temperature = self.coordinator.get_coil_float(
            self._coil_current
        )

        mode = HVACMode.OFF
        if self.coordinator.get_coil_value(self._coil_use_room_sensor) == "ON":
            if (
                self.coordinator.get_coil_value(self._coil_cooling_with_room_sensor)
                == "ON"
            ):
                mode = HVACMode.HEAT_COOL
            else:
                mode = HVACMode.HEAT
        self._attr_hvac_mode = mode

        setpoint_heat = self.coordinator.get_coil_float(self._coil_setpoint_heat)
        setpoint_cool = self.coordinator.get_coil_float(self._coil_setpoint_cool)

        if mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature = None
            self._attr_target_temperature_low = setpoint_heat
            self._attr_target_temperature_high = setpoint_cool
        elif mode == HVACMode.HEAT:
            self._attr_target_temperature = setpoint_heat
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None
        else:
            self._attr_target_temperature = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None

        if prio := self.coordinator.get_coil_value(self._coil_prio):
            if (
                mixing_valve_state := self.coordinator.get_coil_value(
                    self._coil_mixing_valve_state
                )
            ) and mixing_valve_state == 30:
                self._attr_hvac_action = HVACAction.IDLE
            elif prio == "Heat":
                self._attr_hvac_action = HVACAction.HEATING
            elif prio == "Cooling":
                self._attr_hvac_action = HVACAction.COOLING
            else:
                self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_action = None

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self._coil_active_accessory_address:
            return True

        if active_accessory := self.coordinator.get_coil_value(
            self._coil_active_accessory_address
        ):
            return active_accessory == "ON"

        return False
