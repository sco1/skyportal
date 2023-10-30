import adafruit_datetime as dt
import adafruit_requests as requests
from circuitpython_base64 import b64encode

from skyportal.aircraftlib import AircraftState

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

OPENSKY_URL_BASE = "https://opensky-network.org/api/states/all"


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


def build_opensky_request(
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


def parse_opensky_response(opensky_json: dict) -> tuple[list[AircraftState], str]:
    """
    Parse the OpenSky API response into a list of aircraft states, along with the UTC timestamp.

    See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for state vector information.
    """
    api_time = str(dt.datetime.fromtimestamp(opensky_json["time"]))
    return [AircraftState(state_vector) for state_vector in opensky_json["states"]], api_time


def query_opensky(header: dict[str, str], url: str) -> dict[str, t.Any]:  # noqa: D103
    r = requests.get(url=url, headers=header)
    if r.status_code != 200:
        raise RuntimeError(f"Bad response received from OpenSky: {r.status_code}, {r.text}")

    aircraft_data = r.json()
    if aircraft_data is None:
        raise RuntimeError("Empty response received from OpenSky")

    return r.json()  # type: ignore[no-any-return]
