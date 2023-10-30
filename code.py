from __future__ import annotations

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
GEOAPIFY_API_URL_BASE = "https://maps.geoapify.com/v1/staticmap"
MAP_CENTER_LAT = 42.41
MAP_CENTER_LON = -71.17
GRID_WIDTH_MI = 15
MAP_STYLE = "klokantech-basic"

AIO_URL_BASE = f"https://io.adafruit.com/api/v2/{secrets['aio_username']}/integrations/image-formatter"  # noqa: E501

OPENSKY_URL_BASE = "https://opensky-network.org/api/states/all"
REFRESH_INTERVAL_SECONDS = 30

LOCAL_TZ = "America/New_York"
PYPORTAL = PyPortal()
ICON_TILE_SIZE = 16

# Main display element
SKYPORTAL_DISPLAY = board.DISPLAY
MAIN_DISPLAY_GROUP = displayio.Group()
AIRCRAFT_GROUP = displayio.Group()
TIME_LABEL_GROUP = displayio.Group()
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


def set_base_map(grid_bounds: tuple[float, float, float, float], use_default: bool = False) -> None:
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

    if use_default:
        print("Skipping dynamic map tile generation, loading default")
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


def add_time_label() -> label.Label:
    """Add a label for the last update query time."""
    time_label = label.Label(
        font=terminalio.FONT,
        color=0x000000,
        background_color=0xFFFFFF,
        anchor_point=(0, 0),
        anchored_position=(5, 5),
        padding_top=2,
        padding_bottom=2,
        padding_left=2,
        padding_right=2,
    )
    TIME_LABEL_GROUP.append(time_label)
    MAIN_DISPLAY_GROUP.append(TIME_LABEL_GROUP)

    return time_label


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


class AircraftCategory:  # noqa: D101
    NO_INFO = 0
    NO_CATEGORY_INFO = 1
    LIGHT = 2
    SMALL = 3
    LARGE = 4
    HIGH_VORTEX_LARGE = 5
    HEAVY = 6
    HIGH_PERFORMANCE = 7
    ROTORCRAFT = 8
    GLIDER = 9
    LIGHTER_THAN_AIR = 10
    PARACHUTIST = 11
    ULTRALIGHT = 12
    RESERVED = 13
    UAV = 14
    SPACE = 15
    SURFACE_EMERGENCY = 16
    SURFACE_SERVICE = 17
    POINT_OBSTACLE = 18
    CLUSTER_OBSTACLE = 19
    LINE_OBSTACLE = 20


class AircraftState:  # noqa: D101
    icao: str
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
        self.icao = state_vector[0]
        self.lat = state_vector[6]
        self.lon = state_vector[5]
        self.track = state_vector[10]
        self.velocity_mps = state_vector[9]
        self.on_ground = state_vector[8]
        self.baro_altitude_m = state_vector[7]
        self.geo_altitude_m = state_vector[13]
        self.vertical_rate_mps = state_vector[11]
        self.aircraft_category = state_vector[17]

    def is_plottable(self) -> bool:  # noqa: D102
        if self.lat is None:
            return False

        if self.lon is None:
            return False

        if self.track is None:
            return False

        return True


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


class AircraftIcon:  # noqa: D101
    def __init__(
        self,
        icon_sheet: displayio.Bitmap,
        palette: displayio.Palette,
        rotation_resolution_deg: int = 30,
    ) -> None:
        self.icon_sheet = icon_sheet
        self.palette = palette
        self.rotation_resolution_deg = rotation_resolution_deg

    @classmethod
    def from_file(cls, filepath: str, rotation_resolution_deg: int = 30) -> AircraftIcon:
        """
        Load the specified sprite sheet & set background transparency.

        NOTE: Ensure that the sprite sheet file has a palette stored in it whose first color is the
        color of the background; this is the color to be set as transparent in the loaded icons.
        """
        icon_sheet, palette = adafruit_imageload.load(
            filepath,
            bitmap=displayio.Bitmap,
            palette=displayio.Palette,
        )
        palette.make_transparent(0)

        return cls(
            icon_sheet=icon_sheet,
            palette=palette,
            rotation_resolution_deg=rotation_resolution_deg,
        )


BASE_ICON = AircraftIcon.from_file("./airplane_icons.bmp")
AIRCRAFT_ICONS = {
    AircraftCategory.ROTORCRAFT: AircraftIcon.from_file("./heli_icons.bmp"),
}


def redraw_aircraft(
    aircraft: list[AircraftState],
    default_icon: AircraftIcon = BASE_ICON,
    custom_icons: dict[int, AircraftIcon] = AIRCRAFT_ICONS,
    skip_ground: bool = True,
) -> None:
    """
    Clear the currently plotted aircraft icons & redraw from the provided list of aircraft.

    NOTE: Aircraft icons are not drawn if an aircraft's state vector is missing the required
    position & orientation data.
    """
    while len(AIRCRAFT_GROUP):
        AIRCRAFT_GROUP.pop()

    n_unplottable = 0
    n_ground = 0
    for ap in aircraft:
        if not ap.is_plottable():
            n_unplottable += 1
            continue

        if skip_ground and ap.on_ground:
            n_ground += 1
            continue

        icon_x, icon_y = calculate_pixel_position(lat=ap.lat, lon=ap.lon, grid_bounds=grid_bounds)  # type: ignore[arg-type]  # noqa: E501

        icon_to_plot = custom_icons.get(ap.aircraft_category, default_icon)
        tile_index = int(ap.track / icon_to_plot.rotation_resolution_deg)  # type: ignore[operator]
        icon = displayio.TileGrid(
            bitmap=icon_to_plot.icon_sheet,
            pixel_shader=icon_to_plot.palette,
            tile_width=ICON_TILE_SIZE,
            tile_height=ICON_TILE_SIZE,
            default_tile=tile_index,
            x=icon_x,
            y=icon_y,
        )
        AIRCRAFT_GROUP.append(icon)

    n_skipped = n_unplottable + n_ground
    print(
        f"Skipped drawing {n_skipped} aircraft ({n_unplottable} missing data, {n_ground} on ground)"
    )


# Initialization
build_splash()
PYPORTAL.network.connect()
print("Wifi connected")
PYPORTAL.get_local_time(location=LOCAL_TZ)

grid_bounds = build_bounding_box()
set_base_map(grid_bounds=grid_bounds, use_default=True)
time_label = add_time_label()
MAIN_DISPLAY_GROUP.append(AIRCRAFT_GROUP)

opensky_header, opensky_url = build_opensky_request(*grid_bounds)
print(f"\n{'='*40}\nInitialization complete\n{'='*40}\n")

# Main loop
while True:
    aircraft: list[AircraftState] = []
    try:
        print("Requesting aircraft data from OpenSky")
        flight_data = query_opensky(header=opensky_header, url=opensky_url)
        print("Parsing OpenSky API response")
        aircraft, api_time = parse_opensky_response(flight_data)
        print(f"Found {len(aircraft)} aircraft")
    except RuntimeError as e:
        print("Error retrieving flight data from OpenSky", e)
    except (requests.OutOfRetries, TimeoutError):
        print("Request to OpenSky timed out")

    if aircraft:
        print("Updating aircraft locations")
        redraw_aircraft(aircraft)
        time_label.text = f"{api_time}Z"
    else:
        print("No aircraft to draw, skipping redraw")

    next_request_at = dt.datetime.now() + dt.timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    print(f"Sleeping... next refresh at {next_request_at} local")
    time.sleep(REFRESH_INTERVAL_SECONDS)
