"""Austria Transit API client using ÖBB native HAFAS mgate."""
from __future__ import annotations

import logging
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .const import API_BASE_DEFAULT, DEFAULT_DURATION, OEBB_AID

_LOGGER = logging.getLogger(__name__)

_CLIENT = {"id": "OEBB", "type": "WEB", "name": "webapp", "l": "vs_webapp"}

# Amenity/accessibility attribute codes that carry no operational value for commuters
_AMENITY_CODES = {
    "OB", "RO", "OA", "OC", "EF", "FK", "WV", "K2", "SB",
    "A", "AE", "BE", "BH", "BO", "BR", "BT", "BU", "FA",
    "NF", "RK", "RM", "gi", "gc",
}

# Codes that are internal mgate control flags, not human-readable text
_INTERNAL_CODES = {"showAsEmergency"}

# Map trimmed catOut value → our internal product type
_CAT_TO_PRODUCT: dict[str, str] = {
    "RJ": "nationalExpress", "ICE": "nationalExpress",
    "NJ": "nationalExpress", "EN": "nationalExpress",
    "EC": "national", "IC": "national",
    "D": "interregional",
    "REX": "regional", "R": "regional", "CJX": "regional",
    "S": "suburban",
    "BUS": "bus", "OBUS": "bus",
    "U": "subway",
    "STR": "tram", "TRAM": "tram",
}


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return ctx

_SSL_CTX = _build_ssl_context()


class AustriaTransitAPI:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = API_BASE_DEFAULT) -> None:
        self._session = session
        self._url = base_url.rstrip("/")

    def _envelope(self, requests: list[dict]) -> dict:
        return {
            "svcReqL": requests,
            "auth": {"type": "AID", "aid": OEBB_AID},
            "client": _CLIENT,
            "ver": "1.67",
            "lang": "deu",
            "formatted": False,
        }

    async def _post(self, payload: dict) -> dict:
        async with self._session.post(
            self._url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=_SSL_CTX,
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def search_stops(self, query: str) -> list[dict[str, Any]]:
        """Search stops by name. Returns [{id, name, products}]."""
        payload = self._envelope([{
            "meth": "LocMatch",
            "req": {
                "input": {
                    "loc": {"name": query, "type": "S"},
                    "maxLoc": 10,
                    "field": "S",
                },
            },
        }])
        data = await self._post(payload)
        svc = data["svcResL"][0]
        if svc.get("err") != "OK":
            return []
        locs: list[dict] = svc["res"]["match"].get("locL") or []
        return [
            {
                "id": loc["extId"],
                "name": loc["name"],
                "products": _pcls_to_products(loc.get("pCls", 0)),
            }
            for loc in locs
            if loc.get("type") == "S" and loc.get("extId")
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

        direction_stop_id: HAFAS stop ID used as dirLoc — the mgate filters
            server-side to only trips whose route passes through that stop.

        line_filter: comma-separated short line names (e.g. "S2,REX").
            Matched case-insensitively against nameS; OR logic.

        direction_text_filter: substring match on the terminus (dirTxt).
            Only useful when direction_stop_id is not set.
        """
        now = datetime.now()
        req: dict[str, Any] = {
            "type": "DEP",
            "stbLoc": {"extId": stop_id, "type": "S"},
            "maxJny": max_results,
            "date": now.strftime("%Y%m%d"),
            "time": now.strftime("%H%M%S"),
            "dur": duration,
        }
        if direction_stop_id:
            req["dirLoc"] = {"extId": direction_stop_id, "type": "S"}

        data = await self._post(self._envelope([{"meth": "StationBoard", "req": req}]))
        svc = data["svcResL"][0]
        if svc.get("err") != "OK":
            _LOGGER.warning("StationBoard error: %s", svc.get("err"))
            return []

        res = svc["res"]
        common = res.get("common", {})
        prod_list: list[dict] = common.get("prodL", [])
        op_list: list[dict] = common.get("opL", [])
        rem_list: list[dict] = common.get("remL", [])
        him_list: list[dict] = common.get("himL", [])

        line_filters: set[str] = set()
        if line_filter:
            line_filters = {f.strip().lower() for f in line_filter.split(",") if f.strip()}

        departures = []
        for jny in res.get("jnyL", []):
            stb: dict = jny.get("stbStop", {})
            jny_date: str = jny.get("date", now.strftime("%Y%m%d"))

            prod_idx = jny.get("prodX")
            prod = prod_list[prod_idx] if prod_idx is not None and prod_idx < len(prod_list) else {}
            prod_ctx: dict = prod.get("prodCtx", {})

            line_name: str = (prod.get("nameS") or prod.get("name") or "?").strip()
            product: str = _cat_to_product(prod_ctx)

            op_idx = prod.get("oprX")
            operator: str = op_list[op_idx]["name"] if op_idx is not None and op_idx < len(op_list) else ""

            direction: str = jny.get("dirTxt") or ""

            if line_filters and not any(f in line_name.lower() for f in line_filters):
                continue
            if direction_text_filter and direction_text_filter.lower() not in direction.lower():
                continue

            tz_offset = stb.get("dTZOffset")
            tz = timezone(timedelta(minutes=tz_offset)) if tz_offset is not None else None

            planned_dt = _parse_dt(jny_date, stb.get("dTimeS"), tz)
            if planned_dt is None:
                continue
            real_dt = _parse_dt(jny_date, stb.get("dTimeR"), tz) if stb.get("dTimeR") else planned_dt
            when_dt = real_dt

            delay_minutes = 0
            if real_dt != planned_dt:
                delay_minutes = round((real_dt - planned_dt).total_seconds() / 60)

            cancelled = stb.get("dCncl", False) or stb.get("aCncl", False)

            platform = _platform(stb.get("dPltfR") or stb.get("dPltfS"))
            planned_platform = _platform(stb.get("dPltfS"))

            remarks = _extract_remarks(jny.get("msgL", []), rem_list, him_list)

            departures.append({
                "direction": direction,
                "line": line_name,
                "product": product,
                "operator": operator,
                "when": when_dt,
                "planned_when": planned_dt,
                "delay_minutes": delay_minutes,
                "platform": platform,
                "planned_platform": planned_platform,
                "cancelled": cancelled,
                "remarks": remarks,
                "trip_id": jny.get("jid"),
            })

        departures.sort(key=lambda d: d["when"])
        return departures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(date_str: str, time_str: str | None, tz: timezone | None) -> datetime | None:
    if not time_str or not date_str:
        return None
    try:
        h = int(time_str[0:2])
        m = int(time_str[2:4])
        s = int(time_str[4:6]) if len(time_str) >= 6 else 0
        base = datetime.strptime(date_str, "%Y%m%d")
        dt = base + timedelta(hours=h, minutes=m, seconds=s)
        return dt.replace(tzinfo=tz) if tz else dt
    except (ValueError, TypeError, IndexError):
        return None


def _platform(pltf: dict | str | None) -> str | None:
    if pltf is None:
        return None
    if isinstance(pltf, dict):
        return pltf.get("txt")
    return str(pltf)


def _cat_to_product(prod_ctx: dict) -> str:
    cat = (prod_ctx.get("catOut") or prod_ctx.get("catOutS") or "").strip().upper()
    return _CAT_TO_PRODUCT.get(cat, "regional")


def _pcls_to_products(pcls: int) -> list[str]:
    """Convert pCls bitmask to list of product type strings."""
    bits = {1: "nationalExpress", 4: "national", 8: "interregional",
            16: "regional", 32: "suburban", 64: "bus",
            128: "subway", 256: "tram", 512: "onCall"}
    return [name for bit, name in bits.items() if pcls & bit]


def _extract_remarks(msg_list: list[dict], rem_list: list[dict], him_list: list[dict]) -> list[dict]:
    remarks = []
    seen: set[str] = set()

    for msg in msg_list:
        msg_type = msg.get("type")
        if msg_type == "REM":
            idx = msg.get("remX")
            if idx is None or idx >= len(rem_list):
                continue
            rem = rem_list[idx]
            code = rem.get("code", "") or ""
            if code in _AMENITY_CODES or code in _INTERNAL_CODES:
                continue
            text = (rem.get("txtN") or rem.get("txtS") or rem.get("txt") or "").strip()
            if text and text not in seen:
                seen.add(text)
                remarks.append({"code": code, "text": text})
        elif msg_type == "HIM":
            idx = msg.get("himX")
            if idx is None or idx >= len(him_list):
                continue
            him = him_list[idx]
            if not him.get("act", True):
                continue
            text = (him.get("text") or him.get("lead") or him.get("head") or "").strip()
            if text and text not in seen:
                seen.add(text)
                remarks.append({"code": "", "text": text})

    return remarks
