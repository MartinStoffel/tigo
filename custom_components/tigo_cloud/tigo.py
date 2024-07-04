"""Business Logic for Tigo."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import TIGO_URL

_LOGGER = logging.getLogger(__name__)


# Time between updating data
SCAN_INTERVAL = timedelta(minutes=1)


class CookieCache:
    """Manages the cookie / auth bearer and also returns the system."""

    def __init__(self, username: str, password: str, systemid: str) -> None:
        """Initialize the cache."""
        self._username = username
        self._password = password
        self._systemid = systemid
        self._system = None
        self._cookie = None
        self._validTill = datetime(1, 1, 1, tzinfo=timezone.utc)

    async def getAuthHeader(self) -> str:
        """Return the Auth header."""
        cookie = await self.__getCookie()
        return {"accept": "application/json", "Authorization": f"Bearer {cookie.value}"}

    def getSystem(self) -> any:
        """Return the system description."""
        return self._system

    async def getSystemAsync(self) -> any:
        """Renutns sthe system description async, for config_flow."""
        if self._system is None:
            await self.__getCookie()

        return self._system

    def resetCookie(self) -> None:
        """Reset validity to get a new cookie."""
        self._validTill = datetime(1, 1, 1, tzinfo=timezone.utc)

    async def __getCookie(self) -> any:
        """Get the cookie from a web login."""
        now = datetime.now(timezone.utc)
        if self._validTill > now:
            return self._cookie

        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            request = await session.get(TIGO_URL)
            text = await request.text()
            for item in text.split("\n"):
                if "TIGO_CSRF_TOKEN" in item:
                    csfr = item.split('"')[1]
                    break

            formData = {
                "_csrf": csfr,
                "LoginFormModel[login]": self._username,
                "LoginFormModel[password]": self._password,
                "LoginFormModel[remember_me]": "0",
            }

            request = await session.post(TIGO_URL, data=formData)

            if request.status != 200:
                _LOGGER.error("Connection failed")

            for f in session.cookie_jar:
                if f.key == "wssJwt":
                    self._cookie = f
                    break

            request.close()

            if self._system is None:
                query = (
                    "/system/summary/config?system_id="
                    + self._systemid
                    + "&resourceId=config&v=0.1.0&_=0"
                )
                request = await session.get(TIGO_URL + query)
                self._system = await request.json()

        seconds = int(self._cookie["max-age"])
        self._validTill = now + timedelta(seconds=seconds, hours=-1)
        return self._cookie


class TigoData:
    """Manages the cookie / auth bearer and also returns the system."""

    def __init__(self, username: str, password: str, systemid: str) -> None:
        """Initialize the cache."""
        self._cookieCahe = CookieCache(username, password, systemid)
        self._systemId = systemid
        self._lastTime = None
        self._data = {}

    async def fetch_data(self) -> None:
        """Get the data from the web api."""
        authHeader = await self._cookieCahe.getAuthHeader()
        async with aiohttp.ClientSession() as session:
            date = datetime.today().date()
            query = f"/api/v4/system/summary/aggenergy?system_id={self._systemId}&date={date}"
            request = await session.get(TIGO_URL + query, headers=authHeader)
            # auth failed?
            if request.status != 200:
                self._cookieCahe.resetCookie()
                return

            val = await request.json()
            self._data["energyRaw"] = val
            self._data["energy"] = {"dataset": val["dataset"]}

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
                        request = await session.get(
                            TIGO_URL + query, headers=authHeader
                        )
                        self._data[value] = await request.json()
                    except Exception as e:
                        msg = f"{e.__class__} occurred details: {e}"
                        _LOGGER.warning(msg)
                        # nop

    def get_system(self) -> any:
        """Return the system data."""
        return self._cookieCahe.getSystem()

    def get_reading(self, property) -> any:
        """Return readings of property."""
        return self._data.get(property)["dataset"]


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
        return await self.tigo_data.fetch_data()

    def get_panels(self) -> any:
        """Return the panels of the system."""
        system = self.tigo_data.get_system()
        return [x for x in system["system"]["objects"] if x.get("B") == 2]

    def get_reading(self, panelId, property) -> any:
        """Get the actual reaging."""
        reading = self.tigo_data.get_reading(property)
        return reading.get(str(panelId), None)

    def get_data(self) -> any:
        """Get the whole reaging data."""
        return self.htigo_data.get_data()
