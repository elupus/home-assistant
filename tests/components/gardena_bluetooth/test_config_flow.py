"""Test the Gardena Bluetooth config flow."""

import asyncio
from unittest.mock import Mock

from gardena_bluetooth.const import DeviceInformation
from gardena_bluetooth.exceptions import CharacteristicNotFound
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.gardena_bluetooth.const import CONF_PRODUCT_TYPE, DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    MISSING_MANUFACTURER_DATA_SERVICE_INFO,
    MISSING_PRODUCT_SERVICE_INFO,
    MISSING_SERVICE_SERVICE_INFO,
    UNRELATED_SERVICE_INFO,
    UNSUPPORTED_GROUP_SERVICE_INFO,
    WATER_TIMER_SERVICE_INFO,
    WATER_TIMER_UNNAMED_SERVICE_INFO,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "constant_advertisements")


async def test_user_selection(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    inject_bluetooth_service_info(hass, WATER_TIMER_UNNAMED_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_user_selection_replaces_ignored(hass: HomeAssistant) -> None:
    """Test setup from service info cache replaces an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WATER_TIMER_SERVICE_INFO.address,
    )
    entry.source = config_entries.SOURCE_IGNORE
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: WATER_TIMER_SERVICE_INFO.address},
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == WATER_TIMER_SERVICE_INFO.address


async def test_failed_connect(
    hass: HomeAssistant,
    mock_client: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result == snapshot

    mock_client.read_char.side_effect = CharacteristicNotFound("something went wrong")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_no_valid_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test no valid candidates."""

    inject_bluetooth_service_info(hass, UNRELATED_SERVICE_INFO)
    inject_bluetooth_service_info(hass, UNSUPPORTED_GROUP_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "no_devices_found"


@pytest.mark.parametrize(
    "service_info",
    [MISSING_PRODUCT_SERVICE_INFO, MISSING_MANUFACTURER_DATA_SERVICE_INFO],
    ids=["no_product_info", "no_manufacturer_data"],
)
@pytest.mark.parametrize(
    ("raw", "product_type", "title"),
    [
        pytest.param(
            b"\x01\x26\x04\x12\x00\x10\x00",
            "AQUA_CONTOURS",
            "Gardena Aqua Precise",
            id="aqua_precise",
        ),
        pytest.param(
            b"\x01\x26\x04\x11\x00\x02\x00",
            "PRESSURE_TANKS",
            "Gardena Pressure Tanks",
            id="pressure_tank",
        ),
    ],
)
async def test_user_selection_product_from_pnp_id(
    hass: HomeAssistant,
    mock_read_char_raw: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    raw: bytes,
    product_type: str,
    title: str,
) -> None:
    """Test the product type comes from the PnP ID without product advertisements."""
    mock_read_char_raw[DeviceInformation.model_number.unique_id] = b"Model"
    mock_read_char_raw[DeviceInformation.pnp_id.unique_id] = raw

    inject_bluetooth_service_info(hass, service_info)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: service_info.address},
    )
    assert result.get("step_id") == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == title
    assert result.get("data") == {
        CONF_ADDRESS: service_info.address,
        CONF_PRODUCT_TYPE: product_type,
    }
    assert result["result"].unique_id == service_info.address


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"\x01\x4c\x00\x12\x00\x10\x00", id="other_vendor"),
        pytest.param(b"\x01\x26\x04\x0a\x00\x01\x00", id="mower"),
    ],
)
async def test_bluetooth_unsupported_pnp_id(
    hass: HomeAssistant, mock_read_char_raw: dict[str, bytes], raw: bytes | None
) -> None:
    """Test discovery aborts when the PnP ID does not give a supported product."""
    mock_read_char_raw[DeviceInformation.model_number.unique_id] = b"Model"
    if raw is not None:
        mock_read_char_raw[DeviceInformation.pnp_id.unique_id] = raw

    inject_bluetooth_service_info(hass, MISSING_PRODUCT_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))
    assert result.get("step_id") == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unsupported_product"


async def test_bluetooth_scan_service_only(
    hass: HomeAssistant, mock_read_char_raw: dict[str, bytes]
) -> None:
    """Test discovery of a device advertising nothing but the scan service."""
    mock_read_char_raw[DeviceInformation.model_number.unique_id] = b"Model"
    mock_read_char_raw[DeviceInformation.pnp_id.unique_id] = (
        b"\x01\x26\x04\x12\x00\x10\x00"
    )

    inject_bluetooth_service_info(hass, MISSING_MANUFACTURER_DATA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))
    assert result.get("step_id") == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_ADDRESS: MISSING_MANUFACTURER_DATA_SERVICE_INFO.address,
        CONF_PRODUCT_TYPE: "AQUA_CONTOURS",
    }
    assert result["result"].unique_id == MISSING_MANUFACTURER_DATA_SERVICE_INFO.address


async def test_user_selection_manufacturer_id_only(hass: HomeAssistant) -> None:
    """Test selecting a device advertising no scan service."""
    inject_bluetooth_service_info(hass, MISSING_SERVICE_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MISSING_SERVICE_SERVICE_INFO.address},
    )
    assert result.get("step_id") == "confirm"


async def test_bluetooth_manufacturer_id_only(hass: HomeAssistant) -> None:
    """Test discovery of a device advertising no scan service."""
    inject_bluetooth_service_info(hass, MISSING_SERVICE_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))
    assert result.get("step_id") == "confirm"


async def test_no_devices_at_all(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test missing device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "no_devices_found"


@pytest.mark.parametrize(
    ("service_info"), [WATER_TIMER_SERVICE_INFO, WATER_TIMER_UNNAMED_SERVICE_INFO]
)
async def test_bluetooth(
    hass: HomeAssistant, snapshot: SnapshotAssertion, service_info: BluetoothServiceInfo
) -> None:
    """Test bluetooth device discovery."""

    # Inject the service info will trigger the flow to start
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))

    assert result == snapshot

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot


async def test_bluetooth_invalid(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bluetooth device discovery with invalid data."""

    inject_bluetooth_service_info(hass, UNSUPPORTED_GROUP_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=UNSUPPORTED_GROUP_SERVICE_INFO,
    )
    assert result == snapshot


async def test_already_configured_discovery(
    hass: HomeAssistant, get_product_event: asyncio.Event
) -> None:
    """Ensure we can't add the same device twice."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WATER_TIMER_SERVICE_INFO.address,
    )
    entry.source = config_entries.SOURCE_USER
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=WATER_TIMER_SERVICE_INFO,
    )

    assert get_product_event.is_set() is False
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
