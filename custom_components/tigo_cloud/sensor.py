"""Sensors for Tigo."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SYSTEMID, DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_PROPERTIES = {
    "energy": {
        "name": "Energy",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
    "pin": {
        "name": "Power",
        "native_unit_of_measurement": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:solar-power",
    },
    "rssi": {
        "name": "RSSI",
        "native_unit_of_measurement": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:signal-variant",
    },
    "pwm": {
        "name": "PWM",
        "native_unit_of_measurement": None,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:square-wave",
    },
    "temp": {
        "name": "Temperature",
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:thermometer",
    },
    "vin": {
        "name": "Voltage In",
        "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:alpha-v-circle-outline",
    },
    "vout": {
        "name": "Voltage Out",
        "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:alpha-v-circle",
    },
    "iin": {
        "name": "Current In",
        "native_unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:alpha-a-circle-outline",
    },
    "reclaimedPower": {
        "name": "Reclaimed Power",
        "native_unit_of_measurement": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:solar-power-variant",
    },
}

SUMMARY_PROPERTIES = {
    "now": {
        "name": "Current Production",
        "native_unit_of_measurement": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "attr_icon": "mdi:solar-power-variant",
    },
    "hour": {
        "name": "Hourly Production",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
    "day": {
        "name": "Daily Production",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
    "month": {
        "name": "Monthly Production",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
    "year": {
        "name": "Yearly Production",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
    "allTime": {
        "name": "All Time Production",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "attr_icon": "mdi:solar-power-variant-outline",
    },
}


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    coordinator = hass.data[DOMAIN][config.entry_id]

    panels = []
    for panel in coordinator.get_panels():
        if all(key in panel for key in ("A", "C", "T")):
            panels.append(panel)
        else:
            _LOGGER.warning("Skipping panel without id or label: %s", panel)

    # Tigo only sends the data the license of the system covers, so a sensor is
    # added once its data arrives, and never if it does not.
    added: set[str] = set()

    @callback
    def add_new_sensors() -> None:
        """Add the sensors whose data arrived for the first time."""
        entities = []
        for key in PANEL_PROPERTIES:
            if key not in added and coordinator.has_reading(key):
                added.add(key)
                entities += [TigoPanelSensor(panel, coordinator, key) for panel in panels]

        for key in SUMMARY_PROPERTIES:
            if key not in added and coordinator.get_summary(key) is not None:
                added.add(key)
                entities.append(TigoSummarySensor(coordinator, key))

        if "plan" not in added and coordinator.get_plan() is not None:
            added.add("plan")
            entities.append(TigoPlanSensor(coordinator, config.data[CONF_SYSTEMID]))

        if entities:
            add_entities(entities)

    add_new_sensors()
    config.async_on_unload(coordinator.async_add_listener(add_new_sensors))


class TigoSummarySensor(CoordinatorEntity, SensorEntity):
    """The Tigo summary sensor, showing daily, monthly and yearly stats."""

    def __init__(self, coordinator, property) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._property = property
        self._attr_unique_id = DOMAIN + "tigo.summary." + property

        self._attr_name = SUMMARY_PROPERTIES[property]["name"]
        self._attr_native_unit_of_measurement = SUMMARY_PROPERTIES[property][
            "native_unit_of_measurement"
        ]
        self._attr_device_class = SUMMARY_PROPERTIES[property]["device_class"]
        self._attr_state_class = SUMMARY_PROPERTIES[property]["state_class"]
        self._attr_icon = SUMMARY_PROPERTIES[property]["attr_icon"]
        self._attr_suggested_display_precision = SUMMARY_PROPERTIES[property].get(
            "suggested_display_precision"
        )
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update()
        self.async_write_ha_state()

    def update(self) -> None:
        """Update the data values."""
        self._attr_native_value = self.coordinator.get_summary(self._property)


class TigoPlanSensor(CoordinatorEntity, SensorEntity):
    """The Tigo plan of the system, free or premium."""

    _attr_name = "Tigo Plan"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["Free", "Premium"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:license"

    def __init__(self, coordinator, systemid) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = DOMAIN + "tigo.plan." + systemid
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update()
        self.async_write_ha_state()

    def update(self) -> None:
        """Update the data values."""
        self._attr_native_value = self.coordinator.get_plan()


class TigoPanelSensor(CoordinatorEntity, SensorEntity):
    """The Tigo panel sensor."""

    def __init__(self, panel, coordinator, property) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._property = property
        self._panel = panel
        self._attr_unique_id = DOMAIN + "tigo." + panel["T"] + "_" + property

        self._attr_name = panel["C"] + " " + PANEL_PROPERTIES[property]["name"]
        self._attr_native_unit_of_measurement = PANEL_PROPERTIES[property][
            "native_unit_of_measurement"
        ]
        self._attr_device_class = PANEL_PROPERTIES[property]["device_class"]
        self._attr_state_class = PANEL_PROPERTIES[property]["state_class"]
        self._attr_icon = PANEL_PROPERTIES[property]["attr_icon"]
        self._attr_suggested_display_precision = PANEL_PROPERTIES[property].get(
            "suggested_display_precision"
        )
        self._attr_extra_state_attributes = panel
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update()
        self.async_write_ha_state()

    def update(self) -> None:
        """Update the data values."""
        self._attr_native_value = self.coordinator.get_reading(
            self._panel["A"], self._property
        )
