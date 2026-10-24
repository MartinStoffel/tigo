"""The init."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_PASSWORD, CONF_SYSTEMID, CONF_USERNAME, DOMAIN
from .tigo import TigoCoordinator, TigoData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the element."""
    data = TigoData(
        # A session of its own, as it keeps the login cookies. Closed on unload.
        async_create_clientsession(hass),
        config.data.get(CONF_USERNAME),
        config.data.get(CONF_PASSWORD),
        config.data.get(CONF_SYSTEMID),
    )
    coordinator: TigoCoordinator = TigoCoordinator(hass, data)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator

    # Add entities
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
