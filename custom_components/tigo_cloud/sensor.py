"""Sensors for Tigo."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

PANEL_PROPERTIES = {
    "energy": {
        "name": "Energy",
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
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
        "name": "Temperature ",
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
        "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
        "attr_icon": "mdi:solar-power-variant",
    },
}


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigType, add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    coordinator = hass.data[DOMAIN][config.entry_id]

    entities = []
    for panel in coordinator.get_panels():
        for key in PANEL_PROPERTIES.keys():
            entities.append(TigoPanelSensor(panel, coordinator, key))

    add_entities(entities)


class TigoPanelSensor(CoordinatorEntity, SensorEntity):
    """THe Tigo panle sensor."""

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
