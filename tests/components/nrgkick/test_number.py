"""Tests for the NRGkick number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

from nrgkick_api import NRGkickCommandRejectedError
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entities are created."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    number_keys = {
        entry.translation_key
        for entry in entries
        if entry.domain == "number" and entry.translation_key
    }

    assert number_keys == {"current_set", "energy_limit", "phase_count"}


async def test_number_service_calls_update_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test numbers call the API and update state optimistically."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    def get_entity_id(translation_key: str) -> str:
        entity_entry = next(
            entry
            for entry in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if entry.domain == "number" and entry.translation_key == translation_key
        )
        return entity_entry.entity_id

    current_entity_id = get_entity_id("current_set")
    energy_entity_id = get_entity_id("energy_limit")
    phase_entity_id = get_entity_id("phase_count")

    assert (state := hass.states.get(current_entity_id))
    assert float(state.state) == 16.0

    assert (state := hass.states.get(energy_entity_id))
    assert float(state.state) == 0.0

    assert (state := hass.states.get(phase_entity_id))
    assert float(state.state) == 3.0

    async def set_current(current: float) -> float:
        return float(current)

    mock_nrgkick_api.set_current.side_effect = set_current
    mock_nrgkick_api.set_energy_limit.return_value = 10_000
    mock_nrgkick_api.set_phase_count.return_value = 1

    # Device returns old values immediately, but optimistic update should apply.
    mock_nrgkick_api.get_control.return_value["current_set"] = 16.0
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": current_entity_id, "value": 10},
        blocking=True,
    )
    assert (state := hass.states.get(current_entity_id))
    assert float(state.state) == 10.0

    mock_nrgkick_api.get_control.return_value["energy_limit"] = 0
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": energy_entity_id, "value": 10_000},
        blocking=True,
    )
    assert (state := hass.states.get(energy_entity_id))
    assert float(state.state) == 10_000.0

    mock_nrgkick_api.get_control.return_value["phase_count"] = 3
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": phase_entity_id, "value": 1},
        blocking=True,
    )
    assert (state := hass.states.get(phase_entity_id))
    assert float(state.state) == 1.0

    assert mock_nrgkick_api.set_current.await_args_list == [call(10.0)]
    assert mock_nrgkick_api.set_energy_limit.await_args_list == [call(10_000)]
    assert mock_nrgkick_api.set_phase_count.await_args_list == [call(1)]


async def test_number_rejected_by_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the numbers surface device rejection messages and keep state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "number" and entry.translation_key == "phase_count"
    )
    entity_id = entity_entry.entity_id

    mock_nrgkick_api.set_phase_count.side_effect = NRGkickCommandRejectedError(
        "Phase switching is blocked"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": 1},
            blocking=True,
        )

    assert "blocked" in str(err.value)

    assert (state := hass.states.get(entity_id))
    assert float(state.state) == 3.0
