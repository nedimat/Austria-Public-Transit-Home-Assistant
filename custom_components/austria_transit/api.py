"""Austria Transit API client using oebb.transport.rest (HAFAS)."""
from __future__ import annotations

import logging
import ssl
from datetime import datetime
from typing import Any

import aiohttp

from .const import API_BASE, DEFAULT_DURATION

_LOGGER = logging.getLogger(__name__)

# v6.oebb.transport.rest requires TLS but some HA host environments (hardened
# OpenSSL with SECLEVEL=2) reject the server's cipher suites, causing
# SSLV3_ALERT_HANDSHAKE_FAILURE. Lowering to SECLEVEL=1 widens the accepted
# cipher set while keeping certificate verification and hostname checking on.
def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass  # already permissive enough on this platform
    return ctx

_SSL_CTX = _build_ssl_context()


class AustriaTransitAPI:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def search_stops(self, query: str) -> list[dict[str, Any]]:
        """Search stops by name. Returns [{id, name, products}]."""
        url = f"{API_BASE}/locations"
        params = {
            "query": query,
            "results": 10,
            "stops": "true",
            "poi": "false",
            "addresses": "false",
        }
        async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10), ssl=_SSL_CTX) as resp:
            resp.raise_for_status()
            data: list[dict] = await resp.json()

        return [
            {
                "id": loc["id"],
                "name": loc["name"],
                "products": [k for k, v in (loc.get("products") or {}).items() if v],
            }
            for loc in data
            if loc.get("type") == "stop"
        ]

    async def get_departures(
        self,
        stop_id: str,
        direction_stop_id: str | None = None,
        line_filter: str | None = None,
        direction_text_filter: str | None = None,
        max_results: int = 20,
        duration: int = DEFAULT_DURATION,
    ) -> list[dict[str, Any]]:
        """Fetch departures from a stop.

        direction_stop_id: HAFAS stop ID passed as ``direction`` query param.
            The API returns only trips whose route passes through that stop.
            This is the correct way to filter "via" an intermediate stop.

        line_filter: comma-separated line names (e.g. "3,4" or "REX,WB").
            Matched case-insensitively against line.name; a departure is kept
            if it matches ANY of the supplied names (OR logic).

        direction_text_filter: optional substring match on the terminus name
            returned in the ``direction`` field. Only useful when NOT using
            direction_stop_id (the API already filters there).
        """
        url = f"{API_BASE}/stops/{stop_id}/departures"
        params: dict[str, Any] = {
            "results": max_results,
            "duration": duration,
            "stopovers": "false",
            "language": "de",
        }
        if direction_stop_id:
            # The HAFAS direction param accepts a stop ID and returns only trips
            # whose itinerary passes through that stop. No stopovers needed.
            params["direction"] = direction_stop_id

        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15), ssl=_SSL_CTX) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError:
            raise

        raw_departures: list[dict] = data.get("departures", [])

        # Build normalised line filter set for O(1) lookup
        line_filters: set[str] = set()
        if line_filter:
            line_filters = {f.strip().lower() for f in line_filter.split(",") if f.strip()}

        departures = []
        for dep in raw_departures:
            line: dict = dep.get("line") or {}
            direction: str = dep.get("direction") or ""
            line_name: str = line.get("name") or line.get("id") or "?"
            product: str = line.get("product") or ""

            # Multi-line filter: keep if line_name matches any of the filters
            if line_filters and not any(f in line_name.lower() for f in line_filters):
                continue

            # Optional terminus-name substring match (only meaningful without direction_stop_id)
            if direction_text_filter and direction_text_filter.lower() not in direction.lower():
                continue

            when_str: str | None = dep.get("when") or dep.get("plannedWhen")
            planned_str: str | None = dep.get("plannedWhen") or when_str
            delay_seconds: int = dep.get("delay") or 0

            when_dt = _parse_iso(when_str)
            planned_dt = _parse_iso(planned_str)
            if when_dt is None:
                continue

            cancelled = dep.get("prognosisType") == "cancelled"

            remarks = [
                {"code": r.get("code", ""), "text": r.get("text", "")}
                for r in (dep.get("remarks") or [])
                if r.get("type") == "hint" and r.get("text")
            ]

            departures.append({
                "direction": direction,
                "line": line_name,
                "product": product,
                "operator": (line.get("operator") or {}).get("name", ""),
                "when": when_dt,
                "planned_when": planned_dt,
                "delay_minutes": round(delay_seconds / 60) if delay_seconds else 0,
                "platform": dep.get("platform"),
                "planned_platform": dep.get("plannedPlatform"),
                "cancelled": cancelled,
                "remarks": remarks,
                "trip_id": dep.get("tripId"),
            })

        departures.sort(key=lambda d: d["when"])
        return departures


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
