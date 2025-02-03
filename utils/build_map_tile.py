import argparse
import math
import os
import typing as t
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
AIO_USER = os.environ.get("AIO_USER")
if AIO_USER is None:
    raise RuntimeError("Could not locate 'AIO_USER' env var")
AIO_KEY = os.environ.get("AIO_KEY")
if AIO_KEY is None:
    raise RuntimeError("Could not locate 'AIO_KEY' env var")
GEOAPIFY_KEY = os.environ.get("GEOAPIFY_KEY")
if GEOAPIFY_KEY is None:
    raise RuntimeError("Could not locate 'GEOAPIFY_KEY' env var")


SCREEN_RES = {
    "pyportal": (320, 240),
    "feather": (480, 320),
}

GEOAPIFY_API_URL_BASE = "https://maps.geoapify.com/v1/staticmap"
AIO_URL_BASE = f"https://io.adafruit.com/api/v2/{AIO_USER}/integrations/image-formatter"

DEFAULT_CENTER_LAT = 42.41
DEFAULT_CENTER_LON = -71.17
DEFAULT_GRID_WIDTH_MI = 15
MAP_STYLE = "klokantech-basic"


# We have to copy over our helpers since we can't import from Skyportal without having the
# CircuitPython modules installed
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


def build_bounding_box(
    screen_width: int,
    screen_height: int,
    map_center_lat: float,
    map_center_lon: float,
    grid_width_mi: int,
) -> tuple[float, float, float, float]:
    """Calculate the bounding corners of a rectangular grid centered at the specified map center."""
    earth_radius_km = 6378.1

    center_lat_rad = math.radians(map_center_lat)
    center_lon_rad = math.radians(map_center_lon)
    grid_size_km = grid_width_mi * 1.6

    # Calculate distance deltas
    ang_dist = grid_size_km / earth_radius_km
    d_lat = ang_dist
    d_lon = math.asin(math.sin(ang_dist) / math.cos(center_lat_rad))

    # Scale rectangle height from the specified width
    aspect_ratio = screen_width / screen_height
    d_lon *= aspect_ratio

    # Calculate latitude bounds
    min_center_lat_rad = center_lat_rad - d_lat
    max_center_lat_rad = center_lat_rad + d_lat

    # Calculate longitude bounds
    min_center_lon_rad = center_lon_rad - d_lon
    max_center_lon_rad = center_lon_rad + d_lon

    # Convert from radians to degrees
    lat_min = math.degrees(min_center_lat_rad)
    lat_max = math.degrees(max_center_lat_rad)
    lon_min = math.degrees(min_center_lon_rad)
    lon_max = math.degrees(max_center_lon_rad)

    return lat_min, lat_max, lon_min, lon_max


def get_base_map(
    screen_width: int,
    screen_height: int,
    center_lat: float,
    center_lon: float,
    grid_bounds: tuple[float, float, float, float],
) -> None:
    """
    Query Geoapify for the map image with the given parameters.

    If successful, the map tile image is saved to `./tmp/generated_map.bmp`.

    An attempt is made to query the Geoapify API for a map tile at the location specified by the
    specified mapping constants.

    Since Geoapify returns a PNG & CircuitPython needs a BMP, this image is sent to Adafruit IO for
    resizing & conversion.

    NOTE: The request sent to Geoapify specifies an image size 2x that of the display in order to
    shrink down the labels on the final image for better visualization.

    NOTE: AIO image formatter queries are rate limited to 1 per minute.
    """
    lat_min, lat_max, lon_min, lon_max = grid_bounds
    map_params = {
        "apiKey": GEOAPIFY_KEY,
        "style": MAP_STYLE,
        "format": "png",
        "center": f"lonlat:{center_lon},{center_lat}",
        "area": f"rect:{lon_min},{lat_min},{lon_max},{lat_max}",
        "width": screen_width * 2,
        "height": screen_height * 2,
    }
    map_query_url = build_url(GEOAPIFY_API_URL_BASE, map_params)

    adaIO_params = {
        "x-aio-key": AIO_KEY,
        "width": screen_width,
        "height": screen_height,
        "output": "BMP16",
        "url": urlencode(map_query_url),  # Encode so AIO doesn't eat the Geoapify params
    }
    adaIO_query_url = build_url(AIO_URL_BASE, adaIO_params)

    target_dir = Path("./tmp")
    target_dir.mkdir(exist_ok=True)
    dest = target_dir / "generated_map.bmp"

    with httpx.Client() as client:
        print("Sending image request to AIO...")
        r = client.get(adaIO_query_url)

        if r.status_code != httpx.codes.OK:
            raise RuntimeError(f"Bad response received from AIO: {r.status_code}, {r.text}")

        with dest.open("wb") as f:
            for c in r.iter_bytes(chunk_size=2048):
                f.write(c)

    print("Map image successfully written to '{dest}'!")


def main() -> None:  # noqa: D103
    description = "Query Geoapify & AIO for a map tile with the given parameters."
    epilog = "NOTE: AIO image formatter queries are rate limited to 1 per minute."
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument("target", type=str, choices=("pyportal", "feather"))
    parser.add_argument("--center_lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--center_lon", type=float, default=DEFAULT_CENTER_LON)
    parser.add_argument("--grid_width", type=int, default=DEFAULT_GRID_WIDTH_MI)
    args = parser.parse_args()

    width, height = SCREEN_RES[args.target]
    map_bbox = build_bounding_box(
        screen_width=width,
        screen_height=height,
        map_center_lat=args.center_lat,
        map_center_lon=args.center_lon,
        grid_width_mi=args.grid_width,
    )

    get_base_map(
        screen_width=width,
        screen_height=height,
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        grid_bounds=map_bbox,
    )


if __name__ == "__main__":
    main()
