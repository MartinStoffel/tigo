"""Business Logic for Tigo."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import TIGO_URL

_LOGGER = logging.getLogger(__name__)

# Time between updating data
SCAN_INTERVAL = timedelta(minutes=1)


class TigoError(Exception):
    """Error talking to the Tigo cloud."""


class TigoAuthError(TigoError):
    """The Tigo cloud rejected the login."""


class CookieCache:
    """Manages the cookie / auth bearer and also returns the system."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        systemid: str,
    ) -> None:
        """Initialize the cache."""
        self._session = session
        self._username = username
        self._password = password
        self._systemid = systemid
        self._system = None
        self._cookie = None
        self._validTill = datetime(1, 1, 1, tzinfo=timezone.utc)

    async def getAuthHeader(self) -> dict[str, str]:
        """Return the Auth header."""
        cookie = await self.__getCookie()
        return {"accept": "application/json", "Authorization": f"Bearer {cookie.value}"}

    def getSystem(self) -> Any:
        """Return the system description."""
        return self._system

    async def getSystemAsync(self) -> Any:
        """Returns the system description async, for config_flow."""
        if self._system is None:
            await self.__getCookie()

        return self._system

    def resetCookie(self) -> None:
        """Reset validity to get a new cookie."""
        self._validTill = datetime(1, 1, 1, tzinfo=timezone.utc)

    async def getJson(self, query: str, headers: dict[str, str] | None = None) -> Any:
        """Return the JSON answer of a GET request to the Tigo cloud."""
        async with self._session.get(TIGO_URL + query, headers=headers) as response:
            if response.status != 200:
                raise TigoError(f"{query} returned status {response.status}")
            return await response.json()

    async def __getCookie(self) -> Any:
        """Get the cookie from a web login."""
        now = datetime.now(timezone.utc)
        if self._validTill > now:
            return self._cookie

        # Start with an empty jar, else the cookie of an earlier login would hide a
        # rejected one.
        self._session.cookie_jar.clear()

        async with self._session.get(TIGO_URL) as response:
            if response.status != 200:
                raise TigoError(f"Login page returned status {response.status}")
            text = await response.text()

        csrf = None
        for item in text.split("\n"):
            if "TIGO_CSRF_TOKEN" in item:
                csrf = item.split('"')[1]
                break
        if csrf is None:
            raise TigoError("No CSRF token on the login page")

        formData = {
            "_csrf": csrf,
            "LoginFormModel[login]": self._username,
            "LoginFormModel[password]": self._password,
            "LoginFormModel[remember_me]": "0",
        }

        async with self._session.post(TIGO_URL, data=formData) as response:
            status = response.status

        self._cookie = next(
            (f for f in self._session.cookie_jar if f.key == "wssJwt"), None
        )
        if self._cookie is None:
            # A rejected login shows the login form again.
            if status in (200, 401, 403):
                raise TigoAuthError("Login rejected, check username and password")
            raise TigoError(f"Login failed with status {status}")

        if self._system is None:
            query = (
                "/system/summary/config?system_id="
                + self._systemid
                + "&resourceId=config&v=0.1.0&_=0"
            )
            self._system = await self.getJson(query)

        seconds = int(self._cookie["max-age"])
        self._validTill = now + timedelta(seconds=seconds, hours=-1)
        return self._cookie


class TigoData:
    """Manages the cookie / auth bearer and also returns the system."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        systemid: str,
    ) -> None:
        """Initialize the cache."""
        self._cookieCache = CookieCache(session, username, password, systemid)
        self._systemId = systemid
        self._lastTime = None
        self._data = {}
        # Readings that arrived at least once, and readings failing right now.
        self._delivered: set[str] = set()
        self._failing: set[str] = set()

    def _store(self, key: str, value: Any) -> None:
        """Store a reading that arrived."""
        if key in self._failing and key in self._delivered:
            _LOGGER.info("Tigo sends %s again", key)
        self._failing.discard(key)
        self._delivered.add(key)
        self._data[key] = value

    def _drop(self, key: str, err: Exception) -> None:
        """Forget a reading that failed, logged once per failure streak."""
        # Show unknown rather than the reading of an earlier time.
        self._data.pop(key, None)
        if key in self._failing:
            return
        self._failing.add(key)
        # Data the license does not cover always fails, that is no reason to warn.
        level = logging.WARNING if key in self._delivered else logging.DEBUG
        _LOGGER.log(level, "Tigo did not send %s: %s", key, err)

    def get_value(self, graph) -> Any:
        """Return the reading, None if the graph has no solar total."""
        for serie in graph["series"]:
            if serie["id"] == "solar_total":
                result = 0
                for data in serie["data"]:
                    if data[1] is not None:
                        result = data[1]
                return result
        return None

    async def fetch_data(self) -> None:
        """Get the data from the web api."""
        authHeader = await self._cookieCache.getAuthHeader()
        # Today in the Home Assistant time zone, the host may run in UTC.
        date = dt_util.now().date()
        query = f"/api/v4/system/summary/aggenergy?system_id={self._systemId}&date={date}"
        try:
            val = await self._cookieCache.getJson(query, authHeader)
        except TigoError:
            # The login may have expired, log in again on the next update.
            self._cookieCache.resetCookie()
            raise

        self._data["energyRaw"] = val
        self._data["energy"] = {"dataset": val["dataset"]}

        time = self._lastTime

        for x in val["datasetLastData"]:
            time = val["datasetLastData"][x][11:16]
            break
        if self._lastTime != time:
            self._lastTime = time
            for value in (
                "pin",
                "rssi",
                "pwm",
                "temp",
                "vin",
                "vout",
                "iin",
                "reclaimedPower",
            ):
                try:
                    query = f"/api/v4/system/summary/lastvalue?system_id={self._systemId}&resourceId=lastValue-{date}-{value}-{time}&v=0.1.0&_=0"
                    self._store(
                        value, await self._cookieCache.getJson(query, authHeader)
                    )
                except Exception as e:
                    self._drop(value, e)

        # Get summary data
        for agg in ("now", "hour", "day", "month", "year"):
            try:
                query = f"/api/v4/data/aggregate?systemId={self._systemId}&view=gen&output=echart&type=bar&agg={agg}&start={date}&end={date}&reclaimed=true"
                self._store(
                    agg,
                    self.get_value(await self._cookieCache.getJson(query, authHeader)),
                )
            except Exception as e:
                self._drop(agg, e)
        try:
            query = f"/fleet/system/overview/data-lifetime?sysid={self._systemId}&range=lifetime"
            value = await self._cookieCache.getJson(query, authHeader)
            self._store("allTime", value["energy"])
        except Exception as e:
            self._drop("allTime", e)

    def get_system(self) -> Any:
        """Return the system data."""
        return self._cookieCache.getSystem()

    def get_reading(self, property) -> Any:
        """Return readings of property, None if not fetched."""
        reading = self._data.get(property)
        return reading.get("dataset") if reading else None

    def get_summary(self, property) -> Any:
        """Return summary reading."""
        return self._data.get(property)


# see https://developers.home-assistant.io/docs/integration_fetching_data/
class TigoCoordinator(DataUpdateCoordinator):
    """Represents Coordinator for this sensor."""

    def __init__(self, hass: HomeAssistant, tigo_data: TigoData) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="TigoCoordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        self.tigo_data = tigo_data

    async def _async_update_data(self):
        try:
            return await self.tigo_data.fetch_data()
        except TigoError as e:
            # Marks the sensors unavailable until an update succeeds.
            raise UpdateFailed(str(e)) from e

    def get_panels(self) -> Any:
        """Return the panels of the system."""
        system = self.tigo_data.get_system()
        return [x for x in system["system"]["objects"] if x.get("B") == 2]

    def get_reading(self, panelId, property) -> Any:
        """Get the actual reading."""
        reading = self.tigo_data.get_reading(property)
        if reading is None:
            return None
        return reading.get(str(panelId), None)

    def has_reading(self, property) -> bool:
        """Return whether any panel has a reading of property."""
        reading = self.tigo_data.get_reading(property)
        return reading is not None and any(v is not None for v in reading.values())

    def get_summary(self, property) -> Any:
        """Get the summary reading."""
        return self.tigo_data.get_summary(property)
