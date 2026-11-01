"""The init."""

from __future__ import annotations

from awesomeversion import AwesomeVersion

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery_flow, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import (
    CONF_PASSWORD,
    CONF_SYSTEMID,
    CONF_USERNAME,
    DOMAIN,
    NEW_DOMAIN,
    NEW_URL,
    NEW_VERSION,
)
from .tigo import TigoCoordinator, TigoData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the element."""
    await _async_offer_take_over(hass, config)

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


async def _async_offer_take_over(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Offer the system to the Tigo Cloud integration, which replaces this one."""
    try:
        integration = await async_get_integration(hass, NEW_DOMAIN)
    except IntegrationNotFound:
        integration = None
    if integration is None or not (
        integration.version and integration.version >= AwesomeVersion(NEW_VERSION)
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "moved",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url=NEW_URL,
            translation_key="moved",
            translation_placeholders={"version": NEW_VERSION},
        )
        return

    # Tigo Cloud takes over the system and its sensors once the user confirms
    discovery_flow.async_create_flow(
        hass,
        NEW_DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=dict(config.data),
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
