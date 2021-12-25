"""Tests for the Philips TV menu select entities."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the select platform."""
    with patch("homeassistant.components.philips_js.PLATFORMS", [Platform.SELECT]):
        yield


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test the menu select entities."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_menu_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("entity_id", "option", "update"),
    [
        pytest.param(
            "select.philips_tv_style",
            "Natural",
            {14: {"activenode_id": 16}},
            id="parent-node",
        ),
        pytest.param(
            "select.philips_tv_time_zone_queensland",
            "Victoria",
            {6: {"select_item": 1}},
            id="list-node",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    entity_id: str,
    option: str,
    update: dict[int, Any],
) -> None:
    """Test selecting a menu option."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_tv.postMenuItemsSettingsUpdateData.assert_called_once_with(update)
