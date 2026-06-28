"""
Tests for AustriaTransitAPI — mgate HAFAS protocol.

All HTTP calls are mocked — no network access needed.
Run with: pytest tests/
"""
from __future__ import annotations

import copy
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import importlib.util, sys, pathlib

ROOT = pathlib.Path(__file__).parent.parent


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
_parse_dt = _api_mod._parse_dt

from tests.fixtures import (
    LARNHAUSERWEG_ALL,
    LARNHAUSERWEG_VIA_LINZ_HBF,
    LINZ_HBF_WESTBAHN,
    INNSBRUCK_HBF_TRAM,
    REMARKS_WITH_AMENITIES_COMMON,
    REMARKS_MSG_LIST,
    AMENITY_CODES,
    STOP_LARNHAUSERWEG,
    STOP_LINZ_HBF,
    STOP_INNSBRUCK_HBF,
    STOP_INNSBRUCK_BERGISEL,
    _station_board_response,
    _jny,
    _PROD_TRAM_3,
    _LINZ_AG_OP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api(response_json: dict) -> tuple[AustriaTransitAPI, MagicMock]:
    """Return (api, mock_session) where POST always returns response_json."""
    session = MagicMock()
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=response_json)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=cm)

    return AustriaTransitAPI(session), session


def _posted_body(session: MagicMock) -> dict:
    """Extract the JSON body sent to session.post()."""
    return session.post.call_args[1]["json"]


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------

def test_parse_dt_valid():
    from datetime import timezone, timedelta
    tz = timezone(timedelta(hours=2))
    dt = _parse_dt("20260620", "080000", tz)
    assert isinstance(dt, datetime)
    assert dt.hour == 8


def test_parse_dt_none_time():
    assert _parse_dt("20260620", None, None) is None


def test_parse_dt_invalid():
    assert _parse_dt("bad-date", "080000", None) is None


def test_parse_dt_past_midnight():
    """Times > 24:00 (cross-midnight journeys) must be handled."""
    from datetime import timezone, timedelta
    dt = _parse_dt("20260620", "250000", None)
    assert dt is not None
    assert dt.day == 21  # next day


# ---------------------------------------------------------------------------
# Use-case 1: Larnhauserweg → Linz Hbf (tram 3 or 4, via Linz Hbf)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_larnhauserweg_via_linz_hbf_uses_direction_param():
    """API must include dirLoc with the direction stop ID in the POST body."""
    api, session = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(
        STOP_LARNHAUSERWEG,
        direction_stop_id=STOP_LINZ_HBF,
    )

    body = _posted_body(session)
    req = body["svcReqL"][0]["req"]
    assert req.get("dirLoc", {}).get("extId") == STOP_LINZ_HBF

    assert len(result) == 3
    assert all(d["direction"] == "Landgutstraße" for d in result)


@pytest.mark.asyncio
async def test_larnhauserweg_no_direction_returns_all():
    """Without direction_stop_id, dirLoc must be absent and all 5 come back."""
    api, session = _make_api(LARNHAUSERWEG_ALL)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    body = _posted_body(session)
    req = body["svcReqL"][0]["req"]
    assert "dirLoc" not in req
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
    """Line filter '3,4' keeps both trams (OR logic)."""
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
    """Line filter matching is case-insensitive."""
    api, _ = _make_api(LARNHAUSERWEG_ALL)
    result = await api.get_departures(STOP_LARNHAUSERWEG, line_filter="3")
    assert all(d["line"] == "3" for d in result)


# ---------------------------------------------------------------------------
# Use-case 2: Linz Hbf → Wien (Westbahn / REX, not trams)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_linz_hbf_westbahn_filter():
    """Filter to 'WB' keeps only WB 111."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(STOP_LINZ_HBF, line_filter="WB")

    assert len(result) == 1
    assert result[0]["line"] == "WB 111"
    assert result[0]["operator"] == "Westbahn"


@pytest.mark.asyncio
async def test_linz_hbf_westbahn_and_rex():
    """Filter 'WB,REX' returns both long-distance, no trams."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(STOP_LINZ_HBF, line_filter="WB,REX")

    lines = {d["line"] for d in result}
    assert lines == {"WB 111", "REX 1"}
    assert not any(d["product"] == "tram" for d in result)


@pytest.mark.asyncio
async def test_delay_converted_to_minutes():
    """RJ 123 has dTimeS=084500 and dTimeR=085000 → 5 minutes delay."""
    api, _ = _make_api(LINZ_HBF_WESTBAHN)

    result = await api.get_departures(STOP_LINZ_HBF)

    rj = next(d for d in result if d["line"] == "RJ 123")
    assert rj["delay_minutes"] == 5


@pytest.mark.asyncio
async def test_no_real_time_means_zero_delay():
    """When dTimeR is absent, delay_minutes must be 0."""
    api, _ = _make_api(LARNHAUSERWEG_VIA_LINZ_HBF)

    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert all(d["delay_minutes"] == 0 for d in result)


# ---------------------------------------------------------------------------
# Use-case 3: Innsbruck Hbf trams (IVB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_innsbruck_line_filter_excludes_other_lines():
    """Line filter '1' excludes tram 3 (Amras)."""
    api, _ = _make_api(INNSBRUCK_HBF_TRAM)

    result = await api.get_departures(STOP_INNSBRUCK_HBF, line_filter="1")

    assert all(d["line"] == "1" for d in result)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_innsbruck_direction_text_filter():
    """direction_text_filter keeps only Bergisel-bound departures."""
    api, _ = _make_api(INNSBRUCK_HBF_TRAM)

    result = await api.get_departures(
        STOP_INNSBRUCK_HBF,
        direction_text_filter="Bergisel",
    )

    assert len(result) == 2
    assert all(d["direction"] == "Bergisel" for d in result)


@pytest.mark.asyncio
async def test_innsbruck_direction_api_param_sent():
    """direction_stop_id must appear as dirLoc.extId in the POST body."""
    api, session = _make_api(INNSBRUCK_HBF_TRAM)

    await api.get_departures(
        STOP_INNSBRUCK_HBF,
        direction_stop_id=STOP_INNSBRUCK_BERGISEL,
    )

    req = _posted_body(session)["svcReqL"][0]["req"]
    assert req["dirLoc"]["extId"] == STOP_INNSBRUCK_BERGISEL


# ---------------------------------------------------------------------------
# mgate request structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_body_contains_auth():
    """Every request must include auth with the AID."""
    api, session = _make_api(LARNHAUSERWEG_ALL)
    await api.get_departures(STOP_LARNHAUSERWEG)

    body = _posted_body(session)
    assert body["auth"]["type"] == "AID"
    assert body["auth"]["aid"] == _const.OEBB_AID


@pytest.mark.asyncio
async def test_post_body_station_board_method():
    """svcReqL must use method 'StationBoard'."""
    api, session = _make_api(LARNHAUSERWEG_ALL)
    await api.get_departures(STOP_LARNHAUSERWEG)

    body = _posted_body(session)
    assert body["svcReqL"][0]["meth"] == "StationBoard"


@pytest.mark.asyncio
async def test_post_body_stop_id_in_stbloc():
    """stbLoc.extId must be the requested stop ID."""
    api, session = _make_api(LARNHAUSERWEG_ALL)
    await api.get_departures(STOP_LARNHAUSERWEG)

    req = _posted_body(session)["svcReqL"][0]["req"]
    assert req["stbLoc"]["extId"] == STOP_LARNHAUSERWEG


# ---------------------------------------------------------------------------
# Remarks filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_amenity_remarks_filtered_out():
    """OB and RO (amenity codes) must not appear in output."""
    fixture = _station_board_response(
        journeys=[_jny(0, "Landgutstraße", "20260620", "080000",
                       msg_list=REMARKS_MSG_LIST)],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=REMARKS_WITH_AMENITIES_COMMON,
        him_list=[{
            "hid": "1", "act": True,
            "text": "Störung auf der Strecke", "icoX": 0,
        }],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    texts = {r["text"] for r in result[0]["remarks"]}
    assert "Niederflurfahrzeug" not in texts
    assert "Rollstuhlstellplatz" not in texts


@pytest.mark.asyncio
async def test_operational_remarks_kept():
    """Non-amenity remarks and HIM messages must appear."""
    fixture = _station_board_response(
        journeys=[_jny(0, "Landgutstraße", "20260620", "080000",
                       msg_list=REMARKS_MSG_LIST)],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=REMARKS_WITH_AMENITIES_COMMON,
        him_list=[{
            "hid": "1", "act": True,
            "text": "Störung auf der Strecke", "icoX": 0,
        }],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    texts = {r["text"] for r in result[0]["remarks"]}
    assert "Bahnsteigsperre" in texts
    assert "Umleitungsverkehr aktiv" in texts
    assert "Störung auf der Strecke" in texts


@pytest.mark.asyncio
async def test_inactive_him_message_excluded():
    """HIM messages with act=False must be suppressed."""
    fixture = _station_board_response(
        journeys=[_jny(0, "Landgutstraße", "20260620", "080000",
                       msg_list=[{"type": "HIM", "himX": 0}])],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=[],
        him_list=[{"hid": "1", "act": False, "text": "Alte Meldung"}],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result[0]["remarks"] == []


# ---------------------------------------------------------------------------
# Cancelled departure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelled_departure_flagged():
    fixture = _station_board_response(
        journeys=[_jny(0, "Landgutstraße", "20260620", "080000", cancelled=True)],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=[], him_list=[],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result[0]["cancelled"] is True


@pytest.mark.asyncio
async def test_not_cancelled_normally():
    api, _ = _make_api(LARNHAUSERWEG_ALL)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert all(d["cancelled"] is False for d in result)


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_extracted_from_object():
    """dPltfS is a {type, txt} object — txt must be returned as platform."""
    fixture = _station_board_response(
        journeys=[_jny(0, "Wien Hbf", "20260620", "080000", pltf_s="3A")],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=[], him_list=[],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result[0]["platform"] == "3A"
    assert result[0]["planned_platform"] == "3A"


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
# Empty / missing data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_journey_list_returns_empty():
    fixture = _station_board_response(
        journeys=[], prod_list=[], op_list=[], rem_list=[], him_list=[],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result == []


@pytest.mark.asyncio
async def test_missing_time_skips_departure():
    """A journey without dTimeS must be skipped."""
    fixture = _station_board_response(
        journeys=[
            _jny(0, "Landgutstraße", "20260620", "080000", jid="good"),
            # Build a journey with no time
            {
                "jid": "bad", "date": "20260620", "prodX": 0,
                "dirTxt": "Landgutstraße",
                "stbStop": {"locX": 0, "idx": 0, "dTZOffset": 120, "type": "N"},
                "msgL": [],
            },
        ],
        prod_list=[_PROD_TRAM_3],
        op_list=[_LINZ_AG_OP],
        rem_list=[], him_list=[],
    )
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert len(result) == 1
    assert result[0]["trip_id"] == "good"


@pytest.mark.asyncio
async def test_server_error_returns_empty():
    """A non-OK svcResL error must return an empty list, not raise."""
    fixture = {
        "ver": "1.67", "err": "OK",
        "svcResL": [{"meth": "StationBoard", "err": "SVC_NO_RESULT", "res": {}}],
    }
    api, _ = _make_api(fixture)
    result = await api.get_departures(STOP_LARNHAUSERWEG)

    assert result == []
