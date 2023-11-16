import gc

import adafruit_requests as requests
from adafruit_datetime import timedelta
from circuitpython_base64 import b64encode

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


class APIException(RuntimeError):  # noqa: D101
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
        r = requests.get(url=url, headers=header)
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
            raise APIException(f"Error retrieving flight data from {self._name}") from e
        except (requests.OutOfRetries, TimeoutError):
            raise APITimeoutError("Request timed out")

        print(f"Found {len(self.aircraft)} aircraft")


class OpenSky(APIHandlerBase):
    """
    OpenSky Network API handler.

    See: https://openskynetwork.github.io/opensky-api/rest.html for schemas
    See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for state vector information
    """

    _name = "OpenSky"
    _api_url_base = "https://opensky-network.org/api/states/all"

    _api_time_key = "time"
    _aircraft_key = "states"
    _aircraft_converter = AircraftState.from_opensky

    def __init__(self, grid_bounds: tuple[float, float, float, float]) -> None:
        self._url, self._header = self._build_request(*grid_bounds)
        self.aircraft = []

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

        opensky_auth = f"{secrets['opensky_username']}:{secrets['opensky_password']}"
        auth_token = b64encode(opensky_auth.encode("utf-8")).decode("ascii")
        opensky_header = {"Authorization": f"Basic {auth_token}"}

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

    def __init__(self, lat: float, lon: float, radius: int) -> None:
        self._url = f"{self._api_url_base}/lat/{lat}/lon/{lon}/dist/{radius}"
        self.aircraft = []
