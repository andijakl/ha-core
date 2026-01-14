"""Device tracker platform for NRGkick."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.device_tracker import (
    SourceType,
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ALTITUDE
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick device tracker entities."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    data = coordinator.data
    info_data: dict[str, Any] = data.info if data else {}
    general_info: dict[str, Any] = info_data.get("general", {})
    model_type = general_info.get("model_type")

    # Cellular and GPS modules are optional. There is no dedicated API to query
    # module availability, but SIM-capable models include "SIM" in their model
    # type (e.g. "NRGkick Gen2 SIM").
    has_sim_module = isinstance(model_type, str) and "SIM" in model_type.upper()

    if not has_sim_module:
        return

    async_add_entities([NRGkickDeviceTrackerEntity(coordinator, DEVICE_TRACKER)])


@dataclass(frozen=True, kw_only=True)
class NRGkickDeviceTrackerEntityDescription(TrackerEntityDescription):
    """Describes an NRGkick tracker entity."""

    latitude_path: tuple[str, ...]
    longitude_path: tuple[str, ...]
    accuracy_path: tuple[str, ...]
    altitude_path: tuple[str, ...]


DEVICE_TRACKER = NRGkickDeviceTrackerEntityDescription(
    key="device_location",
    translation_key="device_location",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    latitude_path=("info", "gps", "latitude"),
    longitude_path=("info", "gps", "longitude"),
    accuracy_path=("info", "gps", "accuracy"),
    altitude_path=("info", "gps", "altitude"),
)


def _nested_get(container: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = container
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


class NRGkickDeviceTrackerEntity(NRGkickEntity, TrackerEntity):
    """Representation of NRGkick GPS location as a device tracker."""

    entity_description: NRGkickDeviceTrackerEntityDescription

    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        description: NRGkickDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the tracker entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _gps_value(self, path: tuple[str, ...]) -> Any:
        data: NRGkickData | None = self.coordinator.data
        info_data: dict[str, Any] = data.info if data else {}
        return _nested_get(info_data, path)

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        latitude = self._gps_value(self.entity_description.latitude_path)
        if not isinstance(latitude, (int, float)):
            return None
        return float(latitude)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        longitude = self._gps_value(self.entity_description.longitude_path)
        if not isinstance(longitude, (int, float)):
            return None
        return float(longitude)

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device, in meters."""
        accuracy = self._gps_value(self.entity_description.accuracy_path)
        if not isinstance(accuracy, (int, float)):
            return 0
        return float(accuracy)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        altitude = self._gps_value(self.entity_description.altitude_path)
        if not isinstance(altitude, (int, float)):
            altitude_value: float | None = None
        else:
            altitude_value = float(altitude)

        return {
            ATTR_ALTITUDE: altitude_value,
        }
