"""Tests for the Philips TV menu number entities."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MENU_SELECTED

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the number platform."""
    with patch("homeassistant.components.philips_js.PLATFORMS", [Platform.NUMBER]):
        yield


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test the menu number entities."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_menu_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("entity_id", "value", "update"),
    [
        pytest.param(
            "number.philips_tv_picture_brightness",
            30,
            {5: {"value": 30}},
            id="slider",
        ),
        pytest.param(
            "number.philips_tv_picture_white_point_red",
            200,
            {
                13: {
                    "value": 200,
                    "slider_id": "org.droidtv.ui.strings.R.string.MAIN_RED",
                }
            },
            id="multi-slider",
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    entity_id: str,
    value: int,
    update: dict[int, Any],
) -> None:
    """Test setting a menu number value."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_tv.getMenuItemsSettingsCurrentValue.reset_mock()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_tv.postMenuItemsSettingsUpdateData.assert_called_once_with(update)
    # All selected settings are read back, the unknown node 99 is not
    mock_tv.getMenuItemsSettingsCurrentValue.assert_called_once_with(
        MOCK_MENU_SELECTED[:-1]
    )
