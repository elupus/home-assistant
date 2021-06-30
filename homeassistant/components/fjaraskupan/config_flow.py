"""Config flow for Fjäråskupan integration."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .device import UUID_SERVICE

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("mac"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    async with BleakClient(data["mac"]) as client:
        svcs = await client.get_services()
        if not svcs:
            raise CannotConnect

        print("Services:")
        for service in svcs:
            print(service)

    return {"title": "Fjäråskupan"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fjäråskupan."""

    VERSION = 1

    def __init__(self):
        """Initialize conflig flow."""
        self._devices: list[BLEDevice] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            self._devices = await BleakScanner().discover()

            devices = {
                str(device.address): f"{device.name or 'Unknown'} [{device.address}]"
                for device in self._devices
                if str(UUID_SERVICE) in device.metadata["uuids"]
            }
            if devices:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("mac"): vol.In(devices),
                        }
                    ),
                )
            else:
                return self.async_abort(reason="no_devices_found")

        errors = {}

        self.async_set_unique_id(user_input["mac"])
        self._abort_if_unique_id_configured()

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
