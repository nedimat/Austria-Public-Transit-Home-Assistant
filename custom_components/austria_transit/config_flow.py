"""Config flow for Austria Transit integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AustriaTransitAPI
from .const import (
    DOMAIN,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_DIRECTION_FILTER,
    CONF_LINE_FILTER,
    CONF_VIA_STOP,
    CONF_VIA_STOP_ID,
    CONF_VIA_STOP_NAME,
    CONF_MAX_DEPARTURES,
    CONF_SCAN_INTERVAL,
    CONF_API_BASE,
    API_BASE_DEFAULT,
    DEFAULT_MAX_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class AustriaTransitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._stop_candidates: list[dict] = []
        self._via_candidates: list[dict] = []
        self._prefill: dict = {}
        self._pending_data: dict = {}  # holds configure step values while via stop is resolved

    def _api(self) -> AustriaTransitAPI:
        return AustriaTransitAPI(async_get_clientsession(self.hass))

    # ── Step 1: search for departure stop ────────────────────────────────────

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                stops = await self._api().search_stops(user_input["stop_search"])
            except Exception:
                errors["base"] = "cannot_connect"
                stops = []
            if not stops:
                errors["base"] = errors.get("base") or "no_stops_found"
            else:
                self._stop_candidates = stops
                return await self.async_step_pick_stop()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("stop_search"): str}),
            errors=errors,
        )

    # ── Step 2: pick departure stop ───────────────────────────────────────────

    async def async_step_pick_stop(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            selected = next((s for s in self._stop_candidates if s["id"] == user_input["stop"]), None)
            if selected:
                self._prefill = {"stop_id": selected["id"], "stop_name": selected["name"]}
                return await self.async_step_configure()
            return await self.async_step_user()

        return self.async_show_form(
            step_id="pick_stop",
            data_schema=vol.Schema({
                vol.Required("stop"): vol.In({
                    s["id"]: f"{s['name']} ({', '.join(s['products'][:3])})"
                    for s in self._stop_candidates
                }),
            }),
        )

    # ── Step 3: configure filters ─────────────────────────────────────────────

    async def async_step_configure(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._pending_data = user_input
            via_query = (user_input.get(CONF_VIA_STOP) or "").strip()
            if via_query:
                # Resolve the via stop text → search step
                try:
                    candidates = await self._api().search_stops(via_query)
                except Exception:
                    candidates = []
                if not candidates:
                    return self.async_show_form(
                        step_id="configure",
                        data_schema=self._configure_schema(),
                        errors={"via_stop": "no_stops_found"},
                        description_placeholders=self._configure_placeholders(),
                    )
                self._via_candidates = candidates
                if len(candidates) == 1:
                    return await self._create_entry_with_via(candidates[0])
                return await self.async_step_pick_via_stop()
            return await self._create_entry_with_via(None)

        return self.async_show_form(
            step_id="configure",
            data_schema=self._configure_schema(),
            description_placeholders=self._configure_placeholders(),
        )

    def _configure_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Optional(CONF_LINE_FILTER, default=""): str,
            vol.Optional(CONF_VIA_STOP, default=""): str,
            vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
            vol.Optional(CONF_MAX_DEPARTURES, default=DEFAULT_MAX_DEPARTURES): vol.All(int, vol.Range(min=1, max=10)),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=30, max=3600)),
            vol.Optional(CONF_API_BASE, default=API_BASE_DEFAULT): str,
        })

    def _configure_placeholders(self) -> dict:
        return {
            "stop_name": self._prefill.get("stop_name", ""),
            "direction_hint": "z. B. Traun (leer lassen für alle)",
            "line_hint": "z. B. 3 oder REX (leer lassen für alle)",
        }

    # ── Step 4 (optional): pick via stop from search results ─────────────────

    async def async_step_pick_via_stop(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            selected = next((s for s in self._via_candidates if s["id"] == user_input["via_stop"]), None)
            if selected:
                return await self._create_entry_with_via(selected)
            return await self.async_step_pick_via_stop()

        return self.async_show_form(
            step_id="pick_via_stop",
            data_schema=vol.Schema({
                vol.Required("via_stop"): vol.In({
                    s["id"]: f"{s['name']} ({', '.join(s['products'][:3])})"
                    for s in self._via_candidates
                }),
            }),
            description_placeholders={"via_query": self._pending_data.get(CONF_VIA_STOP, "")},
        )

    # ── Entry creation ────────────────────────────────────────────────────────

    async def _create_entry_with_via(self, via_stop: dict | None):
        p = self._pending_data
        data = {
            CONF_STOP_ID: self._prefill["stop_id"],
            CONF_STOP_NAME: self._prefill["stop_name"],
            CONF_LINE_FILTER: p.get(CONF_LINE_FILTER) or "",
            CONF_DIRECTION_FILTER: p.get(CONF_DIRECTION_FILTER) or "",
            CONF_VIA_STOP: p.get(CONF_VIA_STOP) or "",
            CONF_VIA_STOP_ID: via_stop["id"] if via_stop else "",
            CONF_VIA_STOP_NAME: via_stop["name"] if via_stop else "",
            CONF_MAX_DEPARTURES: p.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES),
            CONF_SCAN_INTERVAL: p.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_API_BASE: (p.get(CONF_API_BASE) or API_BASE_DEFAULT).rstrip("/"),
        }
        title = self._prefill["stop_name"]
        if data[CONF_VIA_STOP_NAME]:
            title += f" → {data[CONF_VIA_STOP_NAME]}"
        elif data[CONF_DIRECTION_FILTER]:
            title += f" → {data[CONF_DIRECTION_FILTER]}"

        unique = f"{data[CONF_STOP_ID]}_{data[CONF_VIA_STOP_ID]}_{data[CONF_DIRECTION_FILTER]}_{data[CONF_LINE_FILTER]}"
        await self.async_set_unique_id(unique)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return AustriaTransitOptionsFlow()


class AustriaTransitOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._via_candidates: list[dict] = []
        self._pending: dict = {}

    def _api(self) -> AustriaTransitAPI:
        return AustriaTransitAPI(async_get_clientsession(self.hass))

    def _merged(self) -> dict:
        """Current effective config: data overridden by options."""
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        cur = self._merged()
        if user_input is not None:
            self._pending = user_input
            via_query = (user_input.get(CONF_VIA_STOP) or "").strip()
            cur_via_name = cur.get(CONF_VIA_STOP_NAME, "")

            # Only re-resolve if the user changed the via stop text
            if via_query and via_query != cur_via_name:
                try:
                    candidates = await self._api().search_stops(via_query)
                except Exception:
                    candidates = []
                if not candidates:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._schema(cur),
                        errors={"via_stop": "no_stops_found"},
                    )
                self._via_candidates = candidates
                if len(candidates) == 1:
                    return self._save(candidates[0])
                return await self.async_step_pick_via_stop()

            # Via stop cleared or unchanged
            via_stop = None
            if via_query and via_query == cur_via_name:
                # User kept the same name — keep existing IDs
                via_stop = {"id": cur.get(CONF_VIA_STOP_ID, ""), "name": cur_via_name}
            return self._save(via_stop)

        via_suggested = cur.get(CONF_VIA_STOP_NAME) or cur.get(CONF_VIA_STOP) or ""
        suggested = {
            CONF_LINE_FILTER: cur.get(CONF_LINE_FILTER, ""),
            CONF_VIA_STOP: via_suggested,
            CONF_DIRECTION_FILTER: cur.get(CONF_DIRECTION_FILTER, ""),
            CONF_API_BASE: cur.get(CONF_API_BASE, API_BASE_DEFAULT),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(self._schema(cur), suggested),
        )

    async def async_step_pick_via_stop(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            selected = next((s for s in self._via_candidates if s["id"] == user_input["via_stop"]), None)
            if selected:
                return self._save(selected)
            return await self.async_step_pick_via_stop()

        return self.async_show_form(
            step_id="pick_via_stop",
            data_schema=vol.Schema({
                vol.Required("via_stop"): vol.In({
                    s["id"]: f"{s['name']} ({', '.join(s['products'][:3])})"
                    for s in self._via_candidates
                }),
            }),
        )

    def _save(self, via_stop: dict | None):
        p = self._pending
        cur = self._merged()
        options = {
            CONF_LINE_FILTER: p.get(CONF_LINE_FILTER) or "",
            CONF_DIRECTION_FILTER: p.get(CONF_DIRECTION_FILTER) or "",
            CONF_VIA_STOP: p.get(CONF_VIA_STOP) or "",
            CONF_VIA_STOP_ID: via_stop["id"] if via_stop else "",
            CONF_VIA_STOP_NAME: via_stop["name"] if via_stop else "",
            CONF_MAX_DEPARTURES: p.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES),
            CONF_SCAN_INTERVAL: p.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_API_BASE: (p.get(CONF_API_BASE) or cur.get(CONF_API_BASE) or API_BASE_DEFAULT).rstrip("/"),
        }
        return self.async_create_entry(data=options)

    def _schema(self, cur: dict) -> vol.Schema:
        # Use add_suggested_values_to_schema (called in async_step_init) so that
        # pre-filled values are display hints only — NOT voluptuous defaults.
        # This ensures clearing a field and submitting always sends "" to the handler
        # rather than voluptuous substituting the old value back in.
        return vol.Schema({
            vol.Optional(CONF_LINE_FILTER): str,
            vol.Optional(CONF_VIA_STOP): str,
            vol.Optional(CONF_DIRECTION_FILTER): str,
            vol.Optional(CONF_MAX_DEPARTURES, default=cur.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES)): vol.All(int, vol.Range(min=1, max=10)),
            vol.Optional(CONF_SCAN_INTERVAL, default=cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(int, vol.Range(min=30, max=3600)),
            vol.Optional(CONF_API_BASE): str,
        })
