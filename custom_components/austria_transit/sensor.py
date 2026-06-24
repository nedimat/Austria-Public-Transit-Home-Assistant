"""Sensor platform for Austria Transit."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_STOP_NAME, CONF_VIA_STOP_NAME, CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES, PRODUCT_NAMES
from .coordinator import AustriaTransitCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AustriaTransitCoordinator = entry.runtime_data
    stop_name = entry.data[CONF_STOP_NAME]
    config = {**entry.data, **entry.options}
    max_departures = config.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES)

    entities: list[SensorEntity] = [NextDepartureSensor(coordinator, entry, stop_name)]
    for i in range(1, max_departures):
        entities.append(FollowingDepartureSensor(coordinator, entry, stop_name, i))

    async_add_entities(entities)


def _minutes_until(when: datetime) -> int:
    now = dt_util.now()
    delta = when - now
    return max(0, int(delta.total_seconds() / 60))


def _format_departure(dep: dict) -> str:
    mins = _minutes_until(dep["when"])
    line = dep["line"]
    direction = dep["direction"]
    delay = dep["delay_minutes"]

    if dep["cancelled"]:
        time_str = "CANCELLED"
    elif mins == 0:
        time_str = "jetzt"
    elif mins < 60:
        time_str = f"{mins} min"
    else:
        time_str = dep["when"].strftime("%H:%M")

    result = f"{line} → {direction} ({time_str})"
    if delay > 0 and not dep["cancelled"]:
        result += f" +{delay} min"
    return result


def _build_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Austria Transit",
        model="Departure Monitor",
        entry_type=DeviceEntryType.SERVICE,
    )


class NextDepartureSensor(CoordinatorEntity[AustriaTransitCoordinator], SensorEntity):
    """Primary sensor — next departure with full attribute list for dashboard cards."""

    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AustriaTransitCoordinator,
        entry: ConfigEntry,
        stop_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._stop_name = stop_name
        self._attr_unique_id = f"{entry.entry_id}_next_departure"
        self._attr_name = "Next Departure"
        self._attr_device_info = _build_device_info(entry)

    def _first_departure(self) -> dict | None:
        departures = self.coordinator.data or []
        return departures[0] if departures else None

    @property
    def native_value(self) -> str | None:
        dep = self._first_departure()
        return _format_departure(dep) if dep else "No departures"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        departures = self.coordinator.data or []
        dep = self._first_departure()
        config = {**self._entry.data, **self._entry.options}
        attrs: dict[str, Any] = {
            "stop_name": self._stop_name,
            "via_stop": config.get(CONF_VIA_STOP_NAME) or None,
            "departure_list": _serialise_departures(departures),
        }
        if dep:
            attrs.update({
                "line": dep["line"],
                "direction": dep["direction"],
                "product": PRODUCT_NAMES.get(dep["product"], dep["product"]),
                "operator": dep["operator"],
                "scheduled_time": dep["planned_when"].isoformat() if dep["planned_when"] else None,
                "actual_time": dep["when"].isoformat(),
                "delay_minutes": dep["delay_minutes"],
                "platform": dep["platform"],
                "planned_platform": dep["planned_platform"],
                "cancelled": dep["cancelled"],
                "remarks": [r["text"] for r in dep["remarks"]],
                "minutes_until": _minutes_until(dep["when"]),
            })
        return attrs


class FollowingDepartureSensor(CoordinatorEntity[AustriaTransitCoordinator], SensorEntity):
    """Sensor for departure index N (used for automations / glance cards)."""

    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AustriaTransitCoordinator,
        entry: ConfigEntry,
        stop_name: str,
        index: int,
    ) -> None:
        super().__init__(coordinator)
        self._stop_name = stop_name
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_departure_{index + 1}"
        self._attr_name = f"Departure {index + 1}"
        self._attr_device_info = _build_device_info(entry)

    def _get_departure(self) -> dict | None:
        departures = self.coordinator.data or []
        return departures[self._index] if self._index < len(departures) else None

    @property
    def native_value(self) -> str | None:
        dep = self._get_departure()
        return _format_departure(dep) if dep else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dep = self._get_departure()
        if dep is None:
            return {}
        return {
            "line": dep["line"],
            "direction": dep["direction"],
            "actual_time": dep["when"].isoformat(),
            "delay_minutes": dep["delay_minutes"],
            "platform": dep["platform"],
            "cancelled": dep["cancelled"],
            "minutes_until": _minutes_until(dep["when"]),
        }


def _serialise_departures(departures: list[dict]) -> list[dict]:
    result = []
    for dep in departures:
        result.append({
            "line": dep["line"],
            "direction": dep["direction"],
            "time": dep["when"].strftime("%H:%M"),
            "scheduled_time": dep["planned_when"].strftime("%H:%M") if dep["planned_when"] else None,
            "delay_minutes": dep["delay_minutes"],
            "platform": dep["platform"],
            "planned_platform": dep["planned_platform"],
            "cancelled": dep["cancelled"],
            "remarks": [{"code": r["code"], "text": r["text"]} for r in dep["remarks"]],
            "minutes_until": _minutes_until(dep["when"]),
            "product": dep["product"],
            "operator": dep["operator"],
        })
    return result
