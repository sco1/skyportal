import gc

import adafruit_requests as requests
from adafruit_datetime import timedelta

import skyportal_config
from skyportal.aircraftlib import AircraftState
from skyportal.networklib import APIException, APITimeoutError

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass

ADSBLOL_URL_BASE = "https://api.adsb.lol/v2"


def _build_adsblol_request(lat: float, lon: float, radius: int) -> str:
    """Build the ADSB.lol API request URL for the desired location & search radius."""
    query_url = f"{ADSBLOL_URL_BASE}/lat/{lat}/lon/{lon}/dist/{radius}"

    return query_url


def _parse_adsblol_response(adsblol_json: dict) -> tuple[list[AircraftState], int]:
    """
    Parse the ADSB.lol API response into a list of aircraft states, along with the UTC timestamp.

    See: https://api.adsb.lol/docs#/v2 for field schemas
    See: https://github.com/wiedehopf/readsb/blob/dev/README-json.md for ADSB field descriptions
    """
    api_time = adsblol_json["now"] / 1000  # Server time is given in milliseconds

    # If we're not plotting ground planes don't bother keeping them in memory
    states = []
    for state_vector in adsblol_json["ac"]:
        state = AircraftState.from_adsblol(state_vector)
        if skyportal_config.SKIP_GROUND and not state.is_plottable():
            continue

        states.append(state)

    return states, api_time


def _query_adsblol(url: str) -> dict[str, t.Any]:  # noqa: D103
    gc.collect()
    r = requests.get(url=url)
    if r.status_code != 200:
        raise RuntimeError(f"Bad response received from ADSB.lol: {r.status_code}, {r.text}")

    aircraft_data = r.json()
    if aircraft_data is None:
        raise RuntimeError("Empty response received from ADSB.lol")

    return r.json()  # type: ignore[no-any-return]


class AdsbLol:
    """Handler for ADSB.lol API interactions."""

    _url: str
    refresh_interval: timedelta

    aircraft: list[AircraftState]
    api_time: int

    def __init__(
        self,
        lat: float,
        lon: float,
        radius: int,
        refresh_interval: int = 30,
    ) -> None:
        self._url = _build_adsblol_request(lat=lat, lon=lon, radius=radius)
        self.refresh_interval = timedelta(seconds=refresh_interval)

        self.aircraft = []
        self.api_time = -1

    @property
    def can_draw(self) -> bool:  # noqa: D102
        return bool(len(self.aircraft))

    def update(self) -> None:
        """Aircraft state vector update loop."""
        try:
            print("Requesting aircraft data from ADSB.lol")
            flight_data = _query_adsblol(url=self._url)

            print("Parsing ADSB.lol API response")
            self.aircraft, self.api_time = _parse_adsblol_response(flight_data)
            del flight_data
            gc.collect()
        except RuntimeError as e:
            raise APIException("Error retrieving flight data from ADSB.lol") from e
        except (requests.OutOfRetries, TimeoutError):
            raise APITimeoutError("Request timed out")

        print(f"Found {len(self.aircraft)} aircraft")
