import gc
import math
from collections import OrderedDict

import adafruit_requests as requests
import board
import displayio

from secrets import secrets
from skyportal.networklib import build_url, urlencode
from skyportal_config import GRID_WIDTH_MI, MAP_CENTER_LAT, MAP_CENTER_LON

GEOAPIFY_API_URL_BASE = "https://maps.geoapify.com/v1/staticmap"
MAP_STYLE = "klokantech-basic"

AIO_URL_BASE = f"https://io.adafruit.com/api/v2/{secrets['aio_username']}/integrations/image-formatter"  # noqa: E501

SKYPORTAL_DISPLAY = board.DISPLAY


def build_bounding_box(
    map_center_lat: float = MAP_CENTER_LAT,
    map_center_lon: float = MAP_CENTER_LON,
    grid_width_mi: int = GRID_WIDTH_MI,
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
    aspect_ratio = SKYPORTAL_DISPLAY.width / SKYPORTAL_DISPLAY.height
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


def map_range(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    """Normalize the input value to the specified output range."""
    return int(out_min + (((value - in_min) / (in_max - in_min)) * (out_max - out_min)))


def calculate_pixel_position(
    lat: float,
    lon: float,
    grid_bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    """Map lat/long position to on-screen pixel coordinates."""
    lat_min, lat_max, lon_min, lon_max = grid_bounds

    # Calculate x-coordinate
    x = map_range(lon, lon_min, lon_max, 0, SKYPORTAL_DISPLAY.width)

    # Calculate y-coordinate using the Mercator projection
    lat_rad = math.radians(lat)
    lat_max_rad = math.radians(lat_max)
    lat_min_rad = math.radians(lat_min)
    merc_lat = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    merc_max = math.log(math.tan(math.pi / 4 + lat_max_rad / 2))
    merc_min = math.log(math.tan(math.pi / 4 + lat_min_rad / 2))
    y = map_range(merc_lat, merc_max, merc_min, 0, SKYPORTAL_DISPLAY.height)

    return x, y


def get_base_map(
    grid_bounds: tuple[float, float, float, float],
    request_session: requests.Session,
) -> displayio.OnDiskBitmap:
    """
    Query Geoapify for the base map image.

    An attempt is made to query the Geoapify API for a map tile at the location specified by the
    specified mapping constants. If any part of this process fails, the device will fall back to
    loading the default map tile saved onboard.

    Since Geoapify returns a PNG & PyPortal needs a BMP, this image is sent to Adafruit IO for
    resizing & conversion.

    NOTE: The request sent to Geoapify specifies an image size 2x that of the PyPortal display to
    shrink down the labels on the final image for better visualization.
    """
    lat_min, lat_max, lon_min, lon_max = grid_bounds
    map_params = OrderedDict(
        [
            ("apiKey", secrets["geoapify_key"]),
            ("style", MAP_STYLE),
            ("format", "png"),
            ("center", f"lonlat:{MAP_CENTER_LON},{MAP_CENTER_LAT}"),
            ("area", f"rect:{lon_min},{lat_min},{lon_max},{lat_max}"),
            ("width", SKYPORTAL_DISPLAY.width * 2),
            ("height", SKYPORTAL_DISPLAY.height * 2),
        ]
    )
    map_query_url = build_url(GEOAPIFY_API_URL_BASE, map_params)

    adaIO_params = OrderedDict(
        [
            ("x-aio-key", secrets["aio_key"]),
            ("width", SKYPORTAL_DISPLAY.width),
            ("height", SKYPORTAL_DISPLAY.height),
            ("output", "BMP16"),
            ("url", urlencode(map_query_url)),  # Encode so AdaIO doesn't eat the Geoapify params
        ]
    )
    adaIO_query_url = build_url(AIO_URL_BASE, adaIO_params)

    try:
        print("Requesting map tile from Geoapify via AdaIO")
        r = request_session.get(adaIO_query_url)
        if r.status_code != 200:
            raise RuntimeError(f"Bad response received from AdaIO: {r.status_code}, {r.text}")

        with open("./assets/generated_map.bmp", "wb") as f:
            for chunk in r.iter_content(chunk_size=2048):
                f.write(chunk)

        del r
        gc.collect()
        map_img = displayio.OnDiskBitmap("./assets/generated_map.bmp")
        print("Geoapify map tile successfully generated")
    except Exception as e:
        print("Failed to download map:", e)
        print("Falling back to default tile")
        map_img = displayio.OnDiskBitmap("./assets/default_map.bmp")

    return map_img
