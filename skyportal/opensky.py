from secrets import secrets

import adafruit_requests as requests
from adafruit_datetime import timedelta
from circuitpython_base64 import b64encode

from skyportal.aircraftlib import AircraftState
from skyportal.networklib import build_url

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass

OPENSKY_URL_BASE = "https://opensky-network.org/api/states/all"


class APITimeoutError(TimeoutError):  # noqa: D101
    pass


class APIException(RuntimeError):  # noqa: D101
    pass


def _build_opensky_request(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> tuple[dict[str, str], str]:
    """Build the OpenSky API authorization header & request URL for the desired location."""
    opensky_params = {
        "lamin": lat_min,
        "lamax": lat_max,
        "lomin": lon_min,
        "lomax": lon_max,
        "extended": 1,
    }
    opensky_url = build_url(OPENSKY_URL_BASE, opensky_params)

    opensky_auth = f"{secrets['opensky_username']}:{secrets['opensky_password']}"
    auth_token = b64encode(opensky_auth.encode("utf-8")).decode("ascii")
    opensky_header = {"Authorization": f"Basic {auth_token}"}

    return opensky_header, opensky_url


def _parse_opensky_response(opensky_json: dict) -> tuple[list[AircraftState], int]:
    """
    Parse the OpenSky API response into a list of aircraft states, along with the UTC timestamp.

    See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for state vector information.
    """
    api_time = opensky_json["time"]
    return [AircraftState(state_vector) for state_vector in opensky_json["states"]], api_time


def _query_opensky(header: dict[str, str], url: str) -> dict[str, t.Any]:  # noqa: D103
    r = requests.get(url=url, headers=header)
    if r.status_code != 200:
        raise RuntimeError(f"Bad response received from OpenSky: {r.status_code}, {r.text}")

    aircraft_data = r.json()
    if aircraft_data is None:
        raise RuntimeError("Empty response received from OpenSky")

    return r.json()  # type: ignore[no-any-return]


class OpenSky:
    """Handler for OpenSky API interactions."""

    _header: dict[str, str]
    _url: str
    refresh_interval: timedelta

    aircraft: list[AircraftState]
    api_time: int

    def __init__(
        self,
        grid_bounds: tuple[float, float, float, float],
        refresh_interval: int = 30,
    ) -> None:
        self._header, self._url = _build_opensky_request(*grid_bounds)
        self.refresh_interval = timedelta(seconds=refresh_interval)

        self.aircraft = []
        self.api_time = -1

    def can_draw(self) -> bool:  # noqa: D102
        return bool(len(self.aircraft))

    def update(self) -> None:
        """Aircraft state vector update loop."""
        try:
            print("Requesting aircraft data from OpenSky")
            flight_data = _query_opensky(header=self._header, url=self._url)

            print("Parsing OpenSky API response")
            self.aircraft, self.api_time = _parse_opensky_response(flight_data)
        except RuntimeError as e:
            # Clean this up (e.g. the 502 error most commonly seen dumps a full HTML page)
            raise APIException("Error retrieving flight data from OpenSky") from e
        except (requests.OutOfRetries, TimeoutError):
            raise APITimeoutError("Request timed out")

        print(f"Found {len(self.aircraft)} aircraft")
