"""DataUpdateCoordinator for Austria Transit."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AustriaTransitAPI
from .const import (
    DOMAIN,
    CONF_STOP_ID,
    CONF_DIRECTION_FILTER,
    CONF_LINE_FILTER,
    CONF_VIA_STOP_ID,
    CONF_MAX_DEPARTURES,
    DEFAULT_MAX_DEPARTURES,
)

_LOGGER = logging.getLogger(__name__)


class AustriaTransitCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    def __init__(self, hass: HomeAssistant, api: AustriaTransitAPI, config: dict, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._api = api
        self._stop_id: str = config[CONF_STOP_ID]
        # via_stop_id is passed as the HAFAS `direction` query param (stop ID).
        # The API filters server-side to only trips passing through that stop.
        self._direction_stop_id: str | None = config.get(CONF_VIA_STOP_ID) or None
        # line_filter: comma-separated names, e.g. "3,4" or "REX,WB"
        self._line_filter: str | None = config.get(CONF_LINE_FILTER) or None
        # direction_text_filter: terminus name substring, only used without via stop
        self._direction_text_filter: str | None = config.get(CONF_DIRECTION_FILTER) or None
        self._max_departures: int = config.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self._api.get_departures(
                self._stop_id,
                direction_stop_id=self._direction_stop_id,
                line_filter=self._line_filter,
                direction_text_filter=self._direction_text_filter,
                # Fetch extra to account for client-side line filtering
                max_results=max(self._max_departures * 4, 30),
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Austria Transit API: {err}") from err
