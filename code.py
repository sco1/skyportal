from __future__ import annotations

import time

import adafruit_datetime as dt
import adafruit_requests as requests
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_pyportal import PyPortal

from skyportal.aircraftlib import AIRCRAFT_ICONS, AircraftIcon, AircraftState, BASE_ICON
from skyportal.maplib import build_bounding_box, calculate_pixel_position, get_base_map
from skyportal.networklib import build_opensky_request, parse_opensky_response, query_opensky

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


def set_base_map(grid_bounds: tuple[float, float, float, float], use_default: bool = False) -> None:
    """
    Set the base map image on the PyPortal display.

    An attempt is made to query the Geoapify API for a map tile at the location specified by the
    specified mapping constants. If any part of this process fails, or if `use_default` is `True`,
    the device will fall back to loading the default map tile saved onboard.
    """
    if use_default:
        print("Skipping dynamic map tile generation, loading default")
        map_img = displayio.OnDiskBitmap("./default_map.bmp")
    else:
        map_img = get_base_map(grid_bounds=grid_bounds)

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
