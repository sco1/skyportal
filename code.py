import math
import time
from collections import OrderedDict

import adafruit_datetime as dt
import adafruit_imageload
import adafruit_requests as requests
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_pyportal import PyPortal
from circuitpython_base64 import b64encode

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

# Mapping constants
# If adjusting the centerpoint/zoom, use an image size of 2x the PyPortal dimensions in order to
# shink some of the labels in the resulting image
GEOAPIFY_API_URL_BASE = "https://maps.geoapify.com/v1/staticmap"
MAP_CENTER_LAT = 42.458874
MAP_CENTER_LON = -71.021154
MAP_ZOOM = 9
MAP_STYLE = "klokantech-basic"

AIO_URL_BASE = f"https://io.adafruit.com/api/v2/{secrets['aio_username']}/integrations/image-formatter"  # noqa: E501

OPENSKY_URL_BASE = "https://opensky-network.org/api/states/all"
OPENSKY_GRID_SIZE_MILES = 50
REFRESH_INTERVAL_SECONDS = 120

LOCAL_TZ = "America/New_York"
PYPORTAL = PyPortal()
ICON_TILE_SIZE = 16

# Main display element
SKYPORTAL_DISPLAY = board.DISPLAY
MAIN_DISPLAY_GROUP = displayio.Group()
AIRCRAFT_GROUP = displayio.Group()
SKYPORTAL_DISPLAY.root_group = MAIN_DISPLAY_GROUP


def build_splash() -> None:  # noqa: D103
    splash_display = displayio.Group()
    splash_img = displayio.OnDiskBitmap("/splash.bmp")
    splash_sprite = displayio.TileGrid(splash_img, pixel_shader=splash_img.pixel_shader)
    splash_label = label.Label(
        font=terminalio.FONT,
        color=0xFFFFFF,
        text="Initializing...",
        anchor_point=(0.5, 0.5),
        anchored_position=(SKYPORTAL_DISPLAY.width / 2, SKYPORTAL_DISPLAY.height * 0.9),
    )
    splash_display.append(splash_sprite)
    splash_display.append(splash_label)
    MAIN_DISPLAY_GROUP.append(splash_display)


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


def set_base_map(use_default: bool = False) -> None:
    """
    Set the base map image on the PyPortal display.

    An attempt is made to query the Geoapify API for a map tile at the location specified by the
    module-level map constants. Since Geoapify returns a PNG & PyPortal needs a BMP, this image is
    sent to Adafruit IO for resizing & conversion.

    NOTE: The request sent to Geoapify specifies an image size 2x that of the PyPortal display to
    shrink down the labels on the final image for better visualization.

    If any part of this process fails, or if `use_default` is `True`, the device will fall back to
    loading the default map tile saved onboard.
    """
    map_params = OrderedDict(
        [
            ("apiKey", secrets["geoapify_key"]),
            ("style", MAP_STYLE),
            ("format", "png"),
            ("center", f"lonlat:{MAP_CENTER_LON},{MAP_CENTER_LAT}"),
            ("zoom", MAP_ZOOM),
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

    if use_default:
        print("Skipping dynamic map tile generation")
        map_img = displayio.OnDiskBitmap("./default_map.bmp")
    else:
        try:
            print("Requesting map tile from Geoapify via AdaIO")
            r = requests.get(adaIO_query_url)
            if r.status_code != 200:
                raise RuntimeError(f"Bad response received from AdaIO: {r.status_code}, {r.text}")

            with open("./generated_map.bmp", "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    f.write(chunk)

            map_img = displayio.OnDiskBitmap("./generated_map.bmp")
            print("Geoapify map tile successfully generated")
        except Exception as e:
            print("Failed to download map:", e)
            print("Falling back to default tile")
            map_img = displayio.OnDiskBitmap("./default_map.bmp")

    map_group = displayio.Group()
    map_sprite = displayio.TileGrid(map_img, pixel_shader=map_img.pixel_shader)

    map_group.append(map_sprite)

    MAIN_DISPLAY_GROUP.pop()  # Remove the splash screen
    MAIN_DISPLAY_GROUP.append(map_group)


def build_bounding_box(
    map_center_lat: float = MAP_CENTER_LAT,
    map_center_lon: float = MAP_CENTER_LON,
    grid_size_miles: int = OPENSKY_GRID_SIZE_MILES,
) -> tuple[float, float, float, float]:
    """Calculate the bounding corners of a square grid centered at the specified map center."""
    earth_radius_km = 6378.1

    center_lat_rad = math.radians(map_center_lat)
    center_lon_rad = math.radians(map_center_lon)
    grid_size_km = grid_size_miles * 1.6

    # Calculate distance deltas
    ang_dist = grid_size_km / earth_radius_km
    d_lat = ang_dist
    d_lon = math.asin(math.sin(ang_dist) / math.cos(center_lat_rad))

    aspect_ratio = SKYPORTAL_DISPLAY.width / SKYPORTAL_DISPLAY.height
    if aspect_ratio < 1:
        d_lat *= aspect_ratio
    else:
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


class AircraftState:  # noqa: D101
    lat: float | None
    lon: float | None
    track: float | None
    velocity_mps: float | None
    on_ground: bool
    baro_altitude_m: float | None
    geo_altitude_m: float | None
    vertical_rate_mps: float | None
    aircraft_category: int

    def __init__(self, state_vector: dict) -> None:
        self.lat = state_vector[6]
        self.lon = state_vector[5]
        self.track = state_vector[10]
        self.velocity_mps = state_vector[9]
        self.on_ground = state_vector[8]
        self.baro_altitude_m = state_vector[7]
        self.geo_altitude_m = state_vector[13]
        self.vertical_rate_mps = state_vector[11]
        self.aircraft_category = state_vector[17]

    def is_plottable(self) -> bool:
        if self.lat is None:
            return False

        if self.lon is None:
            return False

        if self.track is None:
            return False

        return True


def parse_opensky_response(opensky_json: dict) -> list[AircraftState]:
    """
    Parse the provided OpenSky API response into a list of aircraft states.

    See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for state vector information.
    """
    return [AircraftState(state_vector) for state_vector in opensky_json["states"]]


def query_opensky(header: dict[str, str], url: str) -> dict[str, t.Any]:  # noqa: D103
    r = requests.get(url=url, headers=header)
    if r.status_code != 200:
        raise RuntimeError(f"Bad response received from OpenSky: {r.status_code}, {r.text}")

    return r.json()  # type: ignore[no-any-return]


def build_aircraft_icons() -> tuple[displayio.Bitmap, displayio.Palette]:
    icon_sheet, palette = adafruit_imageload.load(
        "./aircraft_icons.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
    )
    palette.make_transparent(0)

    MAIN_DISPLAY_GROUP.append(AIRCRAFT_GROUP)
    return icon_sheet, palette


def map_range(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    """Map input value to output range"""
    return int(out_min + (((value - in_min) / (in_max - in_min)) * (out_max - out_min)))


def calculate_pixel_position(
    lat: float,
    lon: float,
    grid_bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
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


# Initialization
build_splash()
PYPORTAL.network.connect()
print("Wifi connected")
PYPORTAL.get_local_time(location=LOCAL_TZ)
set_base_map(use_default=True)
aircraft_icons, palette = build_aircraft_icons()
grid_bounds = build_bounding_box()
opensky_header, opensky_url = build_opensky_request(*grid_bounds)
print(f"\n{'='*40}\nInitialization complete\n{'='*40}\n")

# Main loop
while True:
    aircraft: list[AircraftState] = []
    try:
        print("Requesting aircraft data from OpenSky")
        flight_data = query_opensky(header=opensky_header, url=opensky_url)
        print("Parsing OpenSky API response")
        aircraft = parse_opensky_response(flight_data)
        print(f"Found {len(aircraft)} aircraft")
    except RuntimeError as e:
        print("Error retrieving flight data from OpenSky", e)

    # Purge & redraw aircraft icons
    while len(AIRCRAFT_GROUP):
        AIRCRAFT_GROUP.pop()

    n_skipped = 0
    for ap in aircraft:
        if not ap.is_plottable():
            n_skipped += 1
            continue

        icon_x, icon_y = calculate_pixel_position(lat=ap.lat, lon=ap.lon, grid_bounds=grid_bounds)  # type: ignore[arg-type]  # noqa: E501

        # Aircraft icons are provided in 45 degree increments
        tile_index = int(ap.track / 45)  # type: ignore[operator]
        icon = displayio.TileGrid(
            bitmap=aircraft_icons,
            pixel_shader=palette,
            tile_width=ICON_TILE_SIZE,
            tile_height=ICON_TILE_SIZE,
            default_tile=tile_index,
            x=icon_x,
            y=icon_y,
        )
        AIRCRAFT_GROUP.append(icon)

    print(f"Skipped drawing {n_skipped} aircraft due to missing data")

    next_request_at = dt.datetime.now() + dt.timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    print(f"Sleeping... next refresh at {next_request_at}")
    time.sleep(REFRESH_INTERVAL_SECONDS)
