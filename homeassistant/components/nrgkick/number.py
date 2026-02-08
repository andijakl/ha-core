"""Number platform for NRGkick."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import async_api_call
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


def _get_nested_dict_value(data: object, *keys: str) -> object:
    """Safely get a nested value from dict-like API responses."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _rated_current(data: NRGkickData) -> float:
    """Return the rated current of the device in amps."""
    value = _get_nested_dict_value(data.info, "general", "rated_current")
    if isinstance(value, (int, float)):
        return float(value)

    value = _get_nested_dict_value(data.info, "connector", "max_current")
    if isinstance(value, (int, float)):
        return float(value)

    return 32.0


def _max_phase_count(data: NRGkickData) -> float:
    """Return the maximum supported phase count."""
    value = _get_nested_dict_value(data.info, "connector", "phase_count")
    if isinstance(value, int):
        return float(min(3, max(1, value)))
    return 3.0


@dataclass(frozen=True, kw_only=True)
class NRGkickNumberEntityDescription(NumberEntityDescription):
    """Class describing NRGkick number entities."""

    value_fn: Callable[[NRGkickData], float | None]
    max_value_fn: Callable[[NRGkickData], float]
    set_value_fn: Callable[[NRGkickDataUpdateCoordinator, float], Awaitable[float]]


def _control_number(data: NRGkickData, key: str) -> float | None:
    """Return a numeric control key as float."""
    value = data.control.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


async def _async_set_current_set(
    coordinator: NRGkickDataUpdateCoordinator, value: float
) -> float:
    result = await async_api_call(coordinator.api.set_current(float(value)))
    coordinator.async_update_control_cache({"current_set": result})
    return result


async def _async_set_energy_limit(
    coordinator: NRGkickDataUpdateCoordinator, value: float
) -> float:
    limit = int(value)
    result = await async_api_call(coordinator.api.set_energy_limit(limit))
    coordinator.async_update_control_cache({"energy_limit": result})
    return float(result)


async def _async_set_phase_count(
    coordinator: NRGkickDataUpdateCoordinator, value: float
) -> float:
    phases = int(value)
    result = await async_api_call(coordinator.api.set_phase_count(phases))
    coordinator.async_update_control_cache({"phase_count": result})
    return float(result)


NUMBERS: tuple[NRGkickNumberEntityDescription, ...] = (
    NRGkickNumberEntityDescription(
        key="current_set",
        translation_key="current_set",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=6,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: _control_number(data, "current_set"),
        max_value_fn=_rated_current,
        set_value_fn=_async_set_current_set,
    ),
    NRGkickNumberEntityDescription(
        key="energy_limit",
        translation_key="energy_limit",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        native_min_value=0,
        native_max_value=1_000_000_000,
        native_step=1000,
        mode=NumberMode.BOX,
        value_fn=lambda data: _control_number(data, "energy_limit"),
        max_value_fn=lambda _data: 1_000_000_000,
        set_value_fn=_async_set_energy_limit,
    ),
    NRGkickNumberEntityDescription(
        key="phase_count",
        translation_key="phase_count",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=3,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: _control_number(data, "phase_count"),
        max_value_fn=_max_phase_count,
        set_value_fn=_async_set_phase_count,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick numbers based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        NRGkickNumber(coordinator, description) for description in NUMBERS
    )


class NRGkickNumber(NRGkickEntity, NumberEntity):
    """Representation of a NRGkick number."""

    entity_description: NRGkickNumberEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        entity_description: NRGkickNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_max_value(self) -> float:
        """Return the maximum available value."""
        data = self.coordinator.data
        assert data is not None
        return self.entity_description.max_value_fn(data)

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        data = self.coordinator.data
        assert data is not None
        return self.entity_description.value_fn(data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        await self.entity_description.set_value_fn(self.coordinator, value)
