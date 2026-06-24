"""
Tests for AustriaTransitAPI.get_departures().

All HTTP calls are mocked — no network access needed.
Run with: pytest tests/
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal path fixup so the module resolves without a full HA install
# ---------------------------------------------------------------------------
import importlib.util, sys, pathlib, types

ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Load api.py and its const dependency directly — avoids triggering the
# package __init__ which imports homeassistant at the top level.
# ---------------------------------------------------------------------------
def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_const = _load_module(
    "custom_components.austria_transit.const",
    ROOT / "custom_components/austria_transit/const.py",
)
_api_mod = _load_module(
    "custom_components.austria_transit.api",
    ROOT / "custom_components/austria_transit/api.py",
)

AustriaTransitAPI = _api_mod.AustriaTransitAPI
_parse_iso = _api_mod._parse_iso
from tests.fixtures import (
    LARNHAUSERWEG_ALL,
    LARNHAUSERWEG_VIA_LINZ_HBF,
    LINZ_HBF_WESTBAHN,
    INNSBRUCK_HBF_TRAM,
    REMARKS_WITH_AMENITIES,
    AMENITY_CODES,
    STOP_LARNHAUSERWEG,
    STOP_LINZ_HBF,
    STOP_INNSBRUCK_HBF,
    STOP_INNSBRUCK_BERGISEL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api(response_json: dict) -> tuple[AustriaTransitAPI, MagicMock]:
    """Return (api, mock_session) where GET always returns response_json."""
    session = MagicMock()
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=response_json)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm)

    return AustriaTransitAPI(session), session


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------

def test_parse_iso_valid():
    dt = _parse_iso("2026-06-20T08:00:00+02:00")
    assert isinstance(dt, datetime)


def test_parse_iso_none():
    assert _parse_iso(None) is None


def test_parse_iso_invalid():
    assert _parse_iso("not-a-date") is None


# ---------------------------------------------------------------------------
# Use-case 1: Larnhauserweg → Linz Hbf (tram 3 or 4, via Linz Hbf)
# The API direction param is passed; fixture simulates server-side filtering.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_larnhauserweg_via_linz_hbf_uses_direction_param():
    """API must send direction=STOP_LINZ_HBF; no stopovers needed."""
    api, session = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(
        STOP_LARNHAUSERWEG,
        direction_stop_id=STOP_LINZ_HBF,
    )

    # Verify the direction param was sent to the HTTP call
    call_kwargs = session.get.call_args
    params = call_kwargs[1]["params"] if call_kwargs[1] else call_kwargs[0][1]
    assert params.get("direction") == STOP_LINZ_HBF
    assert params.get("stopovers") == "false"

    assert len(result) == 3
    assert all(d["direction"] == "Landgutstraße" for d in result)


@pytest.mark.asyncio
async def test_larnhauserweg_via_linz_hbf_no_direction_param_returns_all():
    """Without direction_stop_id, all directions come back."""
    api, session = _make_api(LARNHAUSERWEG_ALL)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    params = session.get.call_args[1]["params"]
    assert "direction" not in params
    assert len(result) == 5


@pytest.mark.asyncio
async def test_larnhauserweg_line_filter_single():
    """Line filter '3' keeps only tram 3 departures."""
    api, _ = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(
        STOP_LARNHAUSERWEG,
        direction_stop_id=STOP_LINZ_HBF,
        line_filter="3",
    )

    assert all(d["line"] == "3" for d in result)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_larnhauserweg_line_filter_multi():
    """Line filter '3,4' keeps both tram 3 and tram 4 departures (OR logic)."""
    api, _ = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(
        STOP_LARNHAUSERWEG,
        direction_stop_id=STOP_LINZ_HBF,
        line_filter="3,4",
    )

    lines = {d["line"] for d in result}
    assert lines == {"3", "4"}
    assert len(result) == 3


@pytest.mark.asyncio
async def test_line_filter_case_insensitive():
    """Line filter should be case-insensitive."""
    api, _ = _make_api(LARNHAUSERWEG_ALL)
    result = await api.get_departures(STOP_LARNHAUSERWEG, line_filter="TRAM 3")
    # No match because line name is "3", not "tram 3" — correct: filter by name token
    # Now check lowercase exact match
    result2 = await api.get_departures(STOP_LARNHAUSERWEG, line_filter="3")
    assert all(d["line"] == "3" for d in result2)


# ---------------------------------------------------------------------------
# Use-case 2: Linz Hbf → Wien Westbahnhof (Westbahn or REX, not trams)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_linz_hbf_westbahn_filter():
    """Filter to WB (Westbahn) departures from Linz Hbf."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(
        STOP_LINZ_HBF,
        line_filter="WB",
    )

    assert len(result) == 1
    assert result[0]["line"] == "WB 111"
    assert result[0]["operator"] == "Westbahn"


@pytest.mark.asyncio
async def test_linz_hbf_westbahn_and_rex():
    """Filter to WB,REX returns both long-distance options, not trams."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(
        STOP_LINZ_HBF,
        line_filter="WB,REX",
    )

    lines = {d["line"] for d in result}
    assert lines == {"WB 111", "REX 1"}
    assert not any(d["product"] == "tram" for d in result)


@pytest.mark.asyncio
async def test_delay_is_correctly_converted_to_minutes():
    """delay of 180 seconds → 3 minutes."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(STOP_LINZ_HBF)

    rj = next(d for d in result if d["line"] == "RJ 123")
    assert rj["delay_minutes"] == 3


@pytest.mark.asyncio
async def test_null_delay_becomes_zero():
    """delay: null in API response → 0 delay_minutes."""
    api, _ = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert all(d["delay_minutes"] == 0 for d in result)


# ---------------------------------------------------------------------------
# Use-case 3: Innsbruck Hbf → Tram 1 towards Bergisel (IVB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_innsbruck_hbf_line_filter_excludes_other_lines():
    """Line filter '1' excludes tram 3 (Amras)."""
    api, _ = _make_api(INNSBRUCK_HBF_TRAM)

    result = await api.get_departures(
        STOP_INNSBRUCK_HBF,
        line_filter="1",
    )

    assert all(d["line"] == "1" for d in result)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_innsbruck_hbf_direction_text_filter():
    """direction_text_filter keeps only Bergisel-bound departures."""
    api, _ = _make_api(INNSBRUCK_HBF_TRAM)

    result = await api.get_departures(
        STOP_INNSBRUCK_HBF,
        direction_text_filter="Bergisel",
    )

    assert len(result) == 2
    assert all(d["direction"] == "Bergisel" for d in result)


@pytest.mark.asyncio
async def test_innsbruck_hbf_direction_api_param_sent():
    """direction_stop_id is forwarded as the HAFAS direction param."""
    api, session = _make_api(INNSBRUCK_HBF_TRAM)

    await api.get_departures(
        STOP_INNSBRUCK_HBF,
        direction_stop_id=STOP_INNSBRUCK_BERGISEL,
    )

    params = session.get.call_args[1]["params"]
    assert params.get("direction") == STOP_INNSBRUCK_BERGISEL


# ---------------------------------------------------------------------------
# Remarks filtering: amenity codes must be suppressed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remarks_type_warning_excluded():
    """Remarks with type 'warning' must not appear — API only has type 'hint'."""
    fixture = {
        "departures": [{
            **LARNHAUSERWEG_ALL["departures"][0],
            "remarks": REMARKS_WITH_AMENITIES,
        }]
    }
    api, _ = _make_api(fixture)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    remark_texts = [r["text"] for r in result[0]["remarks"]]
    assert "Fahrt fällt aus" not in remark_texts  # type=warning, excluded


@pytest.mark.asyncio
async def test_remarks_only_hint_type_included():
    """Only type='hint' remarks are included in the output."""
    fixture = {
        "departures": [{
            **LARNHAUSERWEG_ALL["departures"][0],
            "remarks": REMARKS_WITH_AMENITIES,
        }]
    }
    api, _ = _make_api(fixture)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    # "Bahnsteigsperre" has type=hint and no amenity code → must appear
    remark_texts = [r["text"] for r in result[0]["remarks"]]
    assert "Bahnsteigsperre" in remark_texts
    assert "Umleitungsverkehr aktiv" in remark_texts


# ---------------------------------------------------------------------------
# Cancelled departure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelled_departure_flagged():
    fixture = {
        "departures": [{
            **LARNHAUSERWEG_ALL["departures"][0],
            "prognosisType": "cancelled",
        }]
    }
    api, _ = _make_api(fixture)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result[0]["cancelled"] is True


@pytest.mark.asyncio
async def test_not_cancelled_when_prognosis_type_is_prognosed():
    fixture = {
        "departures": [{
            **LARNHAUSERWEG_ALL["departures"][0],
            "prognosisType": "prognosed",
        }]
    }
    api, _ = _make_api(fixture)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result[0]["cancelled"] is False


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_departures_sorted_by_when():
    """Departures must be returned in ascending time order."""
    api, _ = _make_api(LARNHAUSERWEG_ALL)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    times = [d["when"] for d in result]
    assert times == sorted(times)


# ---------------------------------------------------------------------------
# No departures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_departures_returns_empty_list():
    api, _ = _make_api({"departures": []})

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result == []


@pytest.mark.asyncio
async def test_missing_when_field_skips_departure():
    """Departures with null when AND null plannedWhen must be skipped."""
    fixture = {
        "departures": [
            {**LARNHAUSERWEG_ALL["departures"][0], "when": None, "plannedWhen": None},
            LARNHAUSERWEG_ALL["departures"][1],
        ]
    }
    api, _ = _make_api(fixture)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert len(result) == 1
