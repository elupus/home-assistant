"""The Gardena Bluetooth integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import logging

from bleak.backends.device import BLEDevice
from gardena_bluetooth.client import CachedConnection, Client
from gardena_bluetooth.const import AquaContour, DeviceConfiguration, DeviceInformation
from gardena_bluetooth.exceptions import CommunicationFailure
from gardena_bluetooth.parse import ManufacturerData, ProductType, Service

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    DeviceUnavailable,
    GardenaBluetoothConfigEntry,
    GardenaBluetoothCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]
LOGGER = logging.getLogger(__name__)
TIMEOUT = 20.0
DISCONNECT_DELAY = 5


def get_connection(hass: HomeAssistant, address: str) -> CachedConnection:
    """Set up a cached client that keeps connection after last use."""

    def _device_lookup() -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        if not device:
            raise DeviceUnavailable("Unable to find device")
        return device

    return CachedConnection(DISCONNECT_DELAY, _device_lookup)


async def _async_service_info(
    hass, address
) -> AsyncIterator[bluetooth.BluetoothServiceInfoBleak]:
    queue = asyncio.Queue[bluetooth.BluetoothServiceInfoBleak]()

    def _callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        if change != bluetooth.BluetoothChange.ADVERTISEMENT:
            return

        queue.put_nowait(service_info)

    service_info = bluetooth.async_last_service_info(hass, address, True)
    if service_info:
        yield service_info

    cancel = bluetooth.async_register_callback(
        hass,
        _callback,
        {bluetooth.match.ADDRESS: address},
        bluetooth.BluetoothScanningMode.ACTIVE,
    )
    try:
        while True:
            yield await queue.get()
    finally:
        cancel()


async def _async_get_product_type(hass, address: str) -> ProductType:
    data = ManufacturerData()

    async for service_info in _async_service_info(hass, address):
        data.update(service_info.manufacturer_data.get(ManufacturerData.company, b""))
        product_type = ProductType.from_manufacturer_data(data)
        if product_type is not ProductType.UNKNOWN:
            return product_type
    raise AssertionError("Iterator should have been infinite")


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    address = entry.data[CONF_ADDRESS]

    try:
        async with asyncio.timeout(TIMEOUT):
            product_type = await _async_get_product_type(hass, address)
    except TimeoutError as exception:
        raise ConfigEntryNotReady("Unable to find product type") from exception

    client = Client(get_connection(hass, address))
    try:
        sw_version = await client.read_char(DeviceInformation.firmware_version, None)
        manufacturer = await client.read_char(DeviceInformation.manufacturer_name, None)
        model = await client.read_char(DeviceInformation.model_number, None)
        uuids = await client.get_all_characteristics_uuid()

        if DeviceConfiguration.custom_device_name.unique_id in uuids:
            name = await client.read_char(
                DeviceConfiguration.custom_device_name, entry.title
            )
        elif AquaContour.custom_device_name.unique_id in uuids:
            name = await client.read_char(AquaContour.custom_device_name, entry.title)
        else:
            name = entry.title

        if DeviceConfiguration.unix_timestamp.unique_id in uuids:
            await client.update_timestamp(
                DeviceConfiguration.unix_timestamp, dt_util.now()
            )
        elif AquaContour.unix_timestamp.unique_id in uuids:
            await client.update_timestamp(AquaContour.unix_timestamp, dt_util.now())

    except (TimeoutError, CommunicationFailure, DeviceUnavailable) as exception:
        await client.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to device {address} due to {exception}"
        ) from exception

    device = DeviceInfo(
        identifiers={(DOMAIN, address)},
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        name=name,
        sw_version=sw_version,
        manufacturer=manufacturer,
        model=model,
    )

    # Find parsers for this device
    services = Service.services_for_product_type(product_type)
    unique_ids = {
        char.unique_id
        for service in services
        for char in service.characteristics.values()
        if char.uuid in uuids
    }

    coordinator = GardenaBluetoothCoordinator(
        hass, entry, LOGGER, client, unique_ids, device, address
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()

    return unload_ok
