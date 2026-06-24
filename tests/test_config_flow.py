"""
Tests for AustriaTransitConfigFlow and AustriaTransitOptionsFlow.

Mocks the API and the HA config_entries framework to run without a full HA install.
Run with: pytest tests/
"""
from __future__ import annotations

import importlib.util, sys, pathlib, types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Load only const and api without triggering the package __init__
# ---------------------------------------------------------------------------
def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_pkg = "custom_components.austria_transit"
_const = _load(f"{_pkg}.const", ROOT / "custom_components/austria_transit/const.py")
_api_mod = _load(f"{_pkg}.api", ROOT / "custom_components/austria_transit/api.py")


# ---------------------------------------------------------------------------
# Minimal HA stubs required by config_flow.py
# ---------------------------------------------------------------------------
def _stub_ha():
    def _mod(*parts):
        key = ".".join(parts)
        if key in sys.modules:
            return sys.modules[key]
        m = types.ModuleType(key)
        sys.modules[key] = m
        return m

    ha = _mod("homeassistant")
    ce = _mod("homeassistant", "config_entries")
    _mod("homeassistant", "core")
    _mod("homeassistant", "helpers")
    _mod("homeassistant", "helpers", "aiohttp_client")

    class _ConfigFlow:
        VERSION = 1
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)

        def async_show_form(self, *, step_id, data_schema=None, errors=None,
                            description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {},
                    "description_placeholders": description_placeholders or {}}

        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

        def _abort_if_unique_id_configured(self):
            pass

        async def async_set_unique_id(self, uid):
            pass

        @staticmethod
        def async_get_options_flow(config_entry):
            pass

    class _OptionsFlow:
        def async_show_form(self, *, step_id, data_schema=None, errors=None,
                            description_placeholders=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(self, *, data):
            return {"type": "create_entry", "data": data}

        @staticmethod
        def add_suggested_values_to_schema(schema, suggested_values):
            return schema

    ce.ConfigFlow = _ConfigFlow
    ce.OptionsFlow = _OptionsFlow
    ce.ConfigEntry = MagicMock

    ha.core = sys.modules["homeassistant.core"]
    ha.core.callback = lambda f: f

    sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = MagicMock()

_stub_ha()

# Now load config_flow
_cf_mod = _load(f"{_pkg}.config_flow", ROOT / "custom_components/austria_transit/config_flow.py")
AustriaTransitConfigFlow = _cf_mod.AustriaTransitConfigFlow
AustriaTransitOptionsFlow = _cf_mod.AustriaTransitOptionsFlow

from tests.fixtures import STOP_LARNHAUSERWEG, STOP_LINZ_HBF

# ---------------------------------------------------------------------------
# Sample stop search results
# ---------------------------------------------------------------------------
STOPS_ONE = [{"id": STOP_LARNHAUSERWEG, "name": "Leonding Larnhauserweg", "products": ["tram"]}]
STOPS_MANY = [
    {"id": "111", "name": "Linz Hbf", "products": ["train"]},
    {"id": "222", "name": "Linz Hbf West", "products": ["bus"]},
]
VIA_ONE = [{"id": STOP_LINZ_HBF, "name": "Linz/Donau Hbf", "products": ["train", "tram"]}]
VIA_MANY = [
    {"id": STOP_LINZ_HBF, "name": "Linz/Donau Hbf", "products": ["train"]},
    {"id": "8100014",     "name": "Linz/Donau Hbf Vorplatz", "products": ["bus"]},
]


def _flow() -> AustriaTransitConfigFlow:
    f = AustriaTransitConfigFlow()
    f.hass = MagicMock()
    return f


# ---------------------------------------------------------------------------
# Step 1: async_step_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step_user_shows_form_when_no_input():
    f = _flow()
    result = await f.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_step_user_cannot_connect():
    f = _flow()
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(side_effect=Exception("timeout"))
        mock_api_factory.return_value = mock_api
        result = await f.async_step_user({"stop_search": "Linz"})
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_step_user_no_stops_found():
    f = _flow()
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=[])
        mock_api_factory.return_value = mock_api
        result = await f.async_step_user({"stop_search": "xyznonexistent"})
    assert result["errors"]["base"] == "no_stops_found"


@pytest.mark.asyncio
async def test_step_user_one_result_goes_to_pick_stop():
    f = _flow()
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=STOPS_ONE)
        mock_api_factory.return_value = mock_api
        result = await f.async_step_user({"stop_search": "Larnhauserweg"})
    # Should jump to pick_stop form (even with one result, user must confirm)
    assert result["step_id"] == "pick_stop"


# ---------------------------------------------------------------------------
# Step 2: async_step_pick_stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step_pick_stop_shows_form():
    f = _flow()
    f._stop_candidates = STOPS_MANY
    result = await f.async_step_pick_stop()
    assert result["step_id"] == "pick_stop"


@pytest.mark.asyncio
async def test_step_pick_stop_valid_selection_goes_to_configure():
    f = _flow()
    f._stop_candidates = STOPS_MANY
    result = await f.async_step_pick_stop({"stop": "111"})
    assert result["step_id"] == "configure"
    assert f._prefill["stop_id"] == "111"
    assert f._prefill["stop_name"] == "Linz Hbf"


# ---------------------------------------------------------------------------
# Step 3: async_step_configure — no via stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_configure_no_via_creates_entry():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    result = await f.async_step_configure({
        "line_filter": "3,4",
        "via_stop": "",
        "direction_filter": "",
        "max_departures": 5,
        "scan_interval": 60,
    })
    assert result["type"] == "create_entry"
    assert result["data"]["stop_id"] == STOP_LARNHAUSERWEG
    assert result["data"]["line_filter"] == "3,4"
    assert result["data"]["via_stop_id"] == ""


@pytest.mark.asyncio
async def test_configure_via_stop_single_result_creates_entry_directly():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=VIA_ONE)
        mock_api_factory.return_value = mock_api
        result = await f.async_step_configure({
            "line_filter": "3",
            "via_stop": "Linz Hbf",
            "direction_filter": "",
            "max_departures": 5,
            "scan_interval": 60,
        })
    assert result["type"] == "create_entry"
    assert result["data"]["via_stop_id"] == STOP_LINZ_HBF
    assert result["data"]["via_stop_name"] == "Linz/Donau Hbf"
    assert "Linz/Donau Hbf" in result["title"]


@pytest.mark.asyncio
async def test_configure_via_stop_multiple_results_goes_to_pick_via():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=VIA_MANY)
        mock_api_factory.return_value = mock_api
        result = await f.async_step_configure({
            "line_filter": "",
            "via_stop": "Linz Hbf",
            "direction_filter": "",
            "max_departures": 5,
            "scan_interval": 60,
        })
    assert result["step_id"] == "pick_via_stop"
    assert f._via_candidates == VIA_MANY


@pytest.mark.asyncio
async def test_configure_via_stop_not_found_shows_error():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=[])
        mock_api_factory.return_value = mock_api
        result = await f.async_step_configure({
            "line_filter": "",
            "via_stop": "nowhere",
            "direction_filter": "",
            "max_departures": 5,
            "scan_interval": 60,
        })
    assert result["type"] == "form"
    assert result["errors"].get("via_stop") == "no_stops_found"


# ---------------------------------------------------------------------------
# Step 4: async_step_pick_via_stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pick_via_stop_creates_entry():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    f._via_candidates = VIA_MANY
    f._pending_data = {
        "line_filter": "3", "via_stop": "Linz Hbf", "direction_filter": "",
        "max_departures": 5, "scan_interval": 60,
    }
    result = await f.async_step_pick_via_stop({"via_stop": STOP_LINZ_HBF})
    assert result["type"] == "create_entry"
    assert result["data"]["via_stop_id"] == STOP_LINZ_HBF
    assert result["data"]["via_stop_name"] == "Linz/Donau Hbf"


@pytest.mark.asyncio
async def test_pick_via_stop_shows_form_when_no_input():
    f = _flow()
    f._via_candidates = VIA_MANY
    f._pending_data = {"via_stop": "Linz Hbf"}
    result = await f.async_step_pick_via_stop()
    assert result["step_id"] == "pick_via_stop"


# ---------------------------------------------------------------------------
# Entry data contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entry_data_contains_required_keys():
    f = _flow()
    f._prefill = {"stop_id": "123", "stop_name": "Test Stop"}
    result = await f.async_step_configure({
        "line_filter": "3,4",
        "via_stop": "",
        "direction_filter": "Traun",
        "max_departures": 3,
        "scan_interval": 120,
    })
    data = result["data"]
    for key in ("stop_id", "stop_name", "line_filter", "direction_filter",
                "via_stop", "via_stop_id", "via_stop_name",
                "max_departures", "scan_interval"):
        assert key in data, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_entry_title_includes_via_stop_name():
    f = _flow()
    f._prefill = {"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Leonding Larnhauserweg"}
    with patch.object(f, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=VIA_ONE)
        mock_api_factory.return_value = mock_api
        result = await f.async_step_configure({
            "line_filter": "", "via_stop": "Linz Hbf", "direction_filter": "",
            "max_departures": 5, "scan_interval": 60,
        })
    assert "Linz/Donau Hbf" in result["title"]


@pytest.mark.asyncio
async def test_entry_title_includes_direction_when_no_via():
    f = _flow()
    f._prefill = {"stop_id": "123", "stop_name": "Linz Hbf"}
    result = await f.async_step_configure({
        "line_filter": "", "via_stop": "", "direction_filter": "Wien",
        "max_departures": 5, "scan_interval": 60,
    })
    assert "Wien" in result["title"]


# ---------------------------------------------------------------------------
# OptionsFlow
# ---------------------------------------------------------------------------

def _options_flow(data: dict, options: dict | None = None) -> AustriaTransitOptionsFlow:
    flow = AustriaTransitOptionsFlow()
    flow.hass = MagicMock()
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    flow.config_entry = entry
    return flow


@pytest.mark.asyncio
async def test_options_flow_shows_form():
    flow = _options_flow(
        data={"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Larnhauserweg",
              "line_filter": "3", "direction_filter": "", "via_stop": "",
              "via_stop_id": "", "via_stop_name": "", "max_departures": 5, "scan_interval": 60},
    )
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_saves_changed_line_filter():
    flow = _options_flow(
        data={"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Larnhauserweg",
              "line_filter": "3", "direction_filter": "", "via_stop": "",
              "via_stop_id": "", "via_stop_name": "", "max_departures": 5, "scan_interval": 60},
    )
    result = await flow.async_step_init({
        "line_filter": "3,4",
        "via_stop": "",
        "direction_filter": "",
        "max_departures": 5,
        "scan_interval": 60,
    })
    assert result["type"] == "create_entry"
    assert result["data"]["line_filter"] == "3,4"


@pytest.mark.asyncio
async def test_options_flow_clears_via_stop():
    flow = _options_flow(
        data={"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Larnhauserweg",
              "line_filter": "", "direction_filter": "", "via_stop": "Linz Hbf",
              "via_stop_id": STOP_LINZ_HBF, "via_stop_name": "Linz/Donau Hbf",
              "max_departures": 5, "scan_interval": 60},
    )
    result = await flow.async_step_init({
        "line_filter": "",
        "via_stop": "",   # cleared
        "direction_filter": "",
        "max_departures": 5,
        "scan_interval": 60,
    })
    assert result["type"] == "create_entry"
    assert result["data"]["via_stop_id"] == ""
    assert result["data"]["via_stop_name"] == ""


@pytest.mark.asyncio
async def test_options_flow_unchanged_via_stop_keeps_existing_id():
    """If user submits the same via_stop name, keep the stored ID without re-searching."""
    flow = _options_flow(
        data={"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Larnhauserweg",
              "line_filter": "", "direction_filter": "", "via_stop": "Linz Hbf",
              "via_stop_id": STOP_LINZ_HBF, "via_stop_name": "Linz/Donau Hbf",
              "max_departures": 5, "scan_interval": 60},
    )
    result = await flow.async_step_init({
        "line_filter": "",
        "via_stop": "Linz/Donau Hbf",  # same as stored name
        "direction_filter": "",
        "max_departures": 5,
        "scan_interval": 60,
    })
    assert result["type"] == "create_entry"
    assert result["data"]["via_stop_id"] == STOP_LINZ_HBF


@pytest.mark.asyncio
async def test_options_flow_new_via_stop_searches_api():
    flow = _options_flow(
        data={"stop_id": STOP_LARNHAUSERWEG, "stop_name": "Larnhauserweg",
              "line_filter": "", "direction_filter": "", "via_stop": "",
              "via_stop_id": "", "via_stop_name": "", "max_departures": 5, "scan_interval": 60},
    )
    with patch.object(flow, "_api") as mock_api_factory:
        mock_api = MagicMock()
        mock_api.search_stops = AsyncMock(return_value=VIA_ONE)
        mock_api_factory.return_value = mock_api
        result = await flow.async_step_init({
            "line_filter": "",
            "via_stop": "Linz Hbf",
            "direction_filter": "",
            "max_departures": 5,
            "scan_interval": 60,
        })
    assert result["type"] == "create_entry"
    assert result["data"]["via_stop_id"] == STOP_LINZ_HBF
    assert result["data"]["via_stop_name"] == "Linz/Donau Hbf"
