"""Austria Transit integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AustriaTransitAPI
from .const import CONF_API_BASE, CONF_SCAN_INTERVAL, API_BASE_DEFAULT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import AustriaTransitCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

_CARD_URL = "/austria_transit/austria-transit-card.js"
_CARD_FILE = str(Path(__file__).parent / "www" / "austria-transit-card.js")

type AustriaTransitConfigEntry = ConfigEntry[AustriaTransitCoordinator]


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card JS to Lovelace resources if not already present."""
    try:
        resources = hass.data.get("lovelace", {}).get("resources")
        if resources is None:
            _LOGGER.warning("Austria Transit: lovelace resources not available; add %s manually", _CARD_URL)
            return
        await resources.async_get_info()
        if any(item["url"] == _CARD_URL for item in resources.async_items()):
            return
        await resources.async_create_item({"res_type": "module", "url": _CARD_URL})
        _LOGGER.info("Austria Transit: registered Lovelace resource %s", _CARD_URL)
    except Exception:
        _LOGGER.exception("Austria Transit: failed to register Lovelace resource")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await hass.http.async_register_static_paths([
        StaticPathConfig(_CARD_URL, _CARD_FILE, cache_headers=True)
    ])

    async def _do_register(_event=None) -> None:
        await _async_register_lovelace_resource(hass)

    if hass.is_running:
        hass.async_create_task(_do_register())
    else:
        @callback
        def _on_ha_started(event) -> None:
            hass.async_create_task(_do_register())
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AustriaTransitConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    config = {**entry.data, **entry.options}
    api = AustriaTransitAPI(session, base_url=config.get(CONF_API_BASE, API_BASE_DEFAULT))
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = AustriaTransitCoordinator(hass, api, config, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: AustriaTransitConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AustriaTransitConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
