import json
from enum import IntEnum

import httpx

URL_BASE = "https://api.adsb.lol/v2"


class AircraftCategory(IntEnum):
    """
    Map ADSB category codes to integers.

    For downstream simplicity, these integers are mapped to the outputs of the OpenSky Network API.
    API details can be found here: https://openskynetwork.github.io/opensky-api/rest.html#response
    """

    NO_INFO = 0
    A0 = 1
    A1 = 2
    A2 = 3
    A3 = 4
    A4 = 5
    A5 = 6
    A6 = 7
    A7 = 8
    B0 = 1
    B1 = 9
    B2 = 10
    B3 = 11
    B4 = 12
    B5 = 13
    B6 = 14
    B7 = 15
    C0 = 1
    C1 = 16
    C2 = 17
    C3 = 18
    C4 = 19
    C5 = 20


def query_data(lat: float, lon: float, radius: float) -> dict:
    """Execute the desired ADSB.lol query & return the JSON response."""
    query_url = f"{URL_BASE}/lat/{lat}/lon/{lon}/dist/{radius}"
    r = httpx.get(query_url)
    r.raise_for_status()

    return r.json()


def simplify_aircraft(flight_data: list[dict]) -> list[dict]:
    """
    Simplify the ADSB.lol API response into something more Skyportal memory friendly.

    The following cleanup operations are made on the provided aircraft state vectors:
        * All non-airborne flights are discarded
        * Keys are reorganized into a layout that directly matches `skyportal.AircraftState`
        * Value units are converted, where necessary
        * Missing keys are set to `None` if expected to be present
    """
    airborne_flights = []
    for state_vector in flight_data:
        if (baro_alt := state_vector["alt_baro"]) == "ground":
            # Skip airborne aircraft
            continue

        if (callsign := state_vector.get("flight", None)) is None:
            callsign = state_vector.get("r", None)
        if callsign is not None:
            callsign = callsign.strip()

        # Ground track is likely not transmitted on the ground
        # If an aircraft is on the ground it may be transmitting true_heading
        if (track := state_vector.get("track", None)) is None:
            track = state_vector.get("true_heading", None)

        if (alt_geo := state_vector.get("alt_geom", None)) is not None:
            alt_geo *= 0.3048  # Provided in ft

        if (baro_rate := state_vector.get("baro_rate", None)) is not None:
            baro_rate *= 0.3048  # Provided in ft

        simplified_vector = {
            "icao": state_vector["hex"],
            "callsign": callsign,
            "lat": state_vector["lat"],
            "lon": state_vector["lon"],
            "track": track,
            "velocity_mps": state_vector["gs"] * 0.5144,  # Provided in kts
            "on_ground": False,
            "baro_altitude_m": baro_alt,
            "geo_altitude_m": alt_geo,
            "vertical_rate_mps": baro_rate,
            "aircraft_category": AircraftCategory[state_vector.get("category", "NO_INFO")],
        }

        airborne_flights.append(simplified_vector)

    return airborne_flights


def lambda_handler(event, context) -> dict:  # noqa: ANN001 D103
    try:
        params = event["queryStringParameters"]
        full_data = query_data(lat=params["lat"], lon=params["lon"], radius=params["radius"])
    except httpx.HTTPError as e:
        return {
            "statusCode": 400,
            "body": json.dumps(f"HTTP Exception for {e.request.url} - {e}"),
        }
    except KeyError as e:
        return {
            "statusCode": 400,
            "body": json.dumps(str(e)),
        }

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "ac": simplify_aircraft(full_data["ac"]),
                "api_time": full_data["now"] / 1000,  # Server time given in milliseconds
            }
        ),
    }
