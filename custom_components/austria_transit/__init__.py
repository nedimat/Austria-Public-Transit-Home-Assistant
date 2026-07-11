"""Austria Transit integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AustriaTransitAPI
from .const import CONF_API_BASE, CONF_SCAN_INTERVAL, API_BASE_DEFAULT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import AustriaTransitCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

_CARD_URL = "/austria_transit/austria-transit-card.js"
_CARD_FILE = str(Path(__file__).parent / "www" / "austria-transit-card.js")

type AustriaTransitConfigEntry = ConfigEntry[AustriaTransitCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await hass.http.async_register_static_paths([
        StaticPathConfig(_CARD_URL, _CARD_FILE, cache_headers=True)
    ])
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
