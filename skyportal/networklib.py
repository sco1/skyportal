import gc

import adafruit_requests as requests
from adafruit_datetime import datetime, timedelta

import skyportal_config
from secrets import secrets
from skyportal.aircraftlib import AircraftState

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass


class APITimeoutError(TimeoutError):  # noqa: D101
    pass


class APIExceptionError(RuntimeError):  # noqa: D101
    pass


def build_url(base: str, params: dict[str, t.Any]) -> str:
    """Build a url from the provided base & parameter(s)."""
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{param_str}"


def urlencode(url: str) -> str:
    """Encode any non-alphanumeric, non-digit, or chars that aren't `-` or `.` in the given URL."""
    encoded_chars = []
    for c in url:
        if any((c.isalpha(), c.isdigit(), (c in ("-", ".")))):
            encoded_chars.append(c)
        else:
            encoded_chars.append(f"%{ord(c):02X}")

    return "".join(encoded_chars)


class APIHandlerBase:  # noqa: D101
    request_session: requests.Session
    refresh_interval: timedelta = timedelta(seconds=30)

    aircraft: list[AircraftState]
    api_time: float = -1

    _name: str
    _api_url_base: str
    _header: dict[str, str] | None
    _url: str

    _api_time_key: str
    _api_time_converter: t.ClassVar[t.Callable[[t.Any, float], float]] = lambda _, x: x  # Identity
    _aircraft_key: str
    _aircraft_converter: t.Callable[[dict], AircraftState]

    def __init__(self) -> None:
        raise NotImplementedError

    @property
    def can_draw(self) -> bool:  # noqa: D102
        return bool(len(self.aircraft))

    def _query_api(self, url: str, header: dict[str, str] | None = None) -> dict[str, t.Any]:
        gc.collect()
        r = self.request_session.get(url=url, headers=header)
        if r.status_code != 200:
            raise RuntimeError(
                f"Bad response received from {self._name}: {r.status_code}, {r.text}"
            )

        aircraft_data = r.json()
        if aircraft_data is None:
            raise RuntimeError(f"Empty response received from {self._name}")

        return r.json()  # type: ignore[no-any-return]

    def _parse_api_response(self, flight_data: dict) -> tuple[list[AircraftState], float]:
        api_time = self._api_time_converter(flight_data[self._api_time_key])

        states = []
        for state_vector in flight_data[self._aircraft_key]:
            state = self._aircraft_converter(state_vector)
            if skyportal_config.SKIP_GROUND and state.on_ground:
                # If we're not plotting ground planes don't bother keeping them in memory
                continue

            states.append(state)

        return states, api_time

    def update(self) -> None:
        """Aircraft state vector update loop."""
        try:
            print(f"Requesting aircraft data from {self._name}")
            flight_data = self._query_api(header=self._header, url=self._url)

            print(f"Parsing {self._name} API response")
            self.aircraft, self.api_time = self._parse_api_response(flight_data)

            del flight_data
            gc.collect()
        except RuntimeError as e:
            raise APIExceptionError(f"Error retrieving flight data from {self._name}") from e
        except (requests.OutOfRetries, TimeoutError) as e:
            raise APITimeoutError("Request timed out") from e

        print(f"Found {len(self.aircraft)} aircraft")


class OpenSkyTokenManager:
    """
    Token manager for the OpenSky API Oauth2 client credentials flow.

    See: https://openskynetwork.github.io/opensky-api/rest.html#authentication
    Adapted: https://openskynetwork.github.io/opensky-api/rest.html#python-token-manager-example
    """

    _token_url = (
        "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    )
    _token_refresh_margin = timedelta(seconds=30)  # Seconds before expiry to proactively refresh

    def __init__(self, session: requests.Session) -> None:
        self.session = session

        self.token: str | None = None
        self.expires_at: datetime | None = None

    def get_token(self) -> str:
        """Retrieve a valid access token, refreshing if needed."""
        if (self.token and self.expires_at) and (datetime.now() < self.expires_at):
            return self.token

        return self._refresh()

    def _refresh(self) -> str:
        r = self.session.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": secrets["opensky_id"],
                "client_secret": secrets["opensky_secret"],
            },
        )

        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = (
            datetime.now() + timedelta(seconds=expires_in) - self._token_refresh_margin
        )

        return self.token

    def headers(self) -> dict[str, str]:
        """Build request header with a valid bearer token."""
        return {"Authorization": f"Bearer {self.get_token()}"}


class OpenSky(APIHandlerBase):
    """
    OpenSky Network API handler.

    See: https://openskynetwork.github.io/opensky-api/rest.html for schemas
    See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for state vector information
    """

    _name = "OpenSky"
    _api_url_base = "https://opensky-network.org/api/states/all"
    _token_manager: OpenSkyTokenManager

    _api_time_key = "time"
    _aircraft_key = "states"
    _aircraft_converter = AircraftState.from_opensky

    def __init__(
        self, grid_bounds: tuple[float, float, float, float], request_session: requests.Session
    ) -> None:
        self._url, self._header = self._build_request(*grid_bounds)
        self.aircraft = []
        self.request_session = request_session

        self._token_manager = OpenSkyTokenManager(self.request_session)

    def _build_request(
        self, lat_min: float, lat_max: float, lon_min: float, lon_max: float
    ) -> tuple[str, dict[str, str]]:
        """Build the OpenSky API authorization header & request URL for the desired location."""
        opensky_params = {
            "lamin": lat_min,
            "lamax": lat_max,
            "lomin": lon_min,
            "lomax": lon_max,
            "extended": 1,
        }
        opensky_url = build_url(self._api_url_base, opensky_params)
        opensky_header = self._token_manager.headers()

        return opensky_url, opensky_header


class ADSBLol(APIHandlerBase):
    """
    ADSB.lol API handler.

    See: https://api.adsb.lol/docs#/v2 for schemas
    See: https://github.com/wiedehopf/readsb/blob/dev/README-json.md for ADSB field descriptions
    """

    _name = "ADSB.lol"
    _api_url_base = "https://api.adsb.lol/v2"

    _header = None

    _api_time_key = "now"
    _api_time_converter = lambda _, t: t / 1000  # Server time given in milliseconds
    _aircraft_key = "ac"
    _aircraft_converter = AircraftState.from_adsblol

    def __init__(
        self,
        lat: float,
        lon: float,
        radius: int,
        request_session: requests.Session,
    ) -> None:
        self._url = f"{self._api_url_base}/lat/{lat}/lon/{lon}/dist/{radius}"
        self.aircraft = []
        self.request_session = request_session


class FR24(APIHandlerBase):
    """
    Flightradar24 API handler, using the Live Flight Positions Light endpoint.

    See: https://fr24api.flightradar24.com/docs/endpoints/overview#live-flight-positions-light
    """

    _name = "Flightradar24"
    _api_url_base = "https://fr24api.flightradar24.com/api/live/flight-positions/light"

    _api_time_key = ""  # FR24 response does not provide a separate timestamp, need to pull from AC
    _aircraft_key = "data"
    _aircraft_converter = AircraftState.from_fr24

    def __init__(
        self,
        grid_bounds: tuple[float, float, float, float],
        request_session: requests.Session,
    ) -> None:
        self.aircraft = []
        self.request_session = request_session

        lat_min, lat_max, lon_min, lon_max = grid_bounds
        self._url = build_url(
            base=self._api_url_base,
            params={"bounds": (lat_max, lat_min, lon_min, lon_max)},  # API expects N,S,W,E
        )
        self._header = {
            "Accept": "application/json",
            "Accept-Version": "v1",
            "Authorization": f"Bearer {secrets["fr24_token"]}",
        }

    def _parse_api_response(self, flight_data: dict) -> tuple[list[AircraftState], float]:
        # The FR24 API response does not provide a separate timestamp, so this needs to be pulled
        # from an aircraft state vector

        # If no aircraft are present, best we can do is carry the old time forward
        if not flight_data[self._aircraft_key]:
            api_time = self.api_time
        else:
            dtstr = flight_data[self._aircraft_key][0]
            api_dt = datetime.fromisoformat(dtstr)
            api_time = api_dt.timestamp()

        states = []
        for state_vector in flight_data[self._aircraft_key]:
            state = self._aircraft_converter(state_vector)
            if skyportal_config.SKIP_GROUND and state.on_ground:
                # If we're not plotting ground planes don't bother keeping them in memory
                continue

            states.append(state)

        return states, api_time


class ProxyAPI(APIHandlerBase):
    """
    Proxy API handler.

    For authentication, the API is assumed to expect an key provided in the `"x-api-key"` header.

    API is assumed to expect three parameters:
        * `lat`, center latitude, decimal degrees
        * `lon`, denter longitude, decimal degrees
        * `radius`, search radius, miles

    API is expected to return two parameters:
        * `"ac"` - A list of state vectors, as dictionaries, whose kv pairs map to `AircraftState`
        * `"api_time"` - UTC epoch time, seconds, may be a float
    """

    _name = "Proxy API"
    _api_url_base = secrets["proxy_api_url"]

    _api_time_key = "api_time"
    _aircraft_key = "ac"
    _aircraft_converter = AircraftState.from_proxy

    def __init__(
        self, lat: float, lon: float, radius: int, request_session: requests.Session
    ) -> None:
        self._url, self._header = self._build_request(lat=lat, lon=lon, radius=radius)
        self.aircraft = []
        self.request_session = request_session

    def _build_request(self, lat: float, lon: float, radius: int) -> tuple[str, dict[str, str]]:
        """Build the OpenSky API authorization header & request URL for the desired location."""
        proxy_params = {
            "lat": lat,
            "lon": lon,
            "radius": radius,
        }
        proxy_url = build_url(self._api_url_base, proxy_params)
        proxy_header = {"x-api-key": secrets["proxy_api_key"]}

        return proxy_url, proxy_header
