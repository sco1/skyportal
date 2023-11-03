import os

import adafruit_datetime as dt
import adafruit_touchscreen
import board
import displayio
import terminalio
from adafruit_bitmapsaver import save_pixels
from adafruit_display_text import label

from constants import GEO_ALTITUDE_THRESHOLD_M, SKIP_GROUND
from skyportal.aircraftlib import (
    AIRCRAFT_ICONS,
    AircraftIcon,
    AircraftState,
    BASE_ICON,
    ICON_TILE_SIZE,
)
from skyportal.maplib import calculate_pixel_position, get_base_map

SKYPORTAL_DISPLAY = board.DISPLAY

SPLASH = "./assets/splash.bmp"
DEFAULT_BASE_MAP = "./assets/default_map.bmp"


class ScreenshotHandler:
    """Handle screenshot saving rotation, saving up to a maximum of `n_screenshots` per location."""

    n_screenshots: int
    _dest: str
    _log_str: str

    def __init__(self, n_screenshots: int = 3, use_sd: bool = True):
        self.n_screenshots = n_screenshots

        if use_sd:
            self._dest = "/sd/"
            self._log_str = "Saving screenshot to SD card"
        else:
            self._dest = "./"
            self._log_str = "Saving screenshot to internal storage"

        print(f"Screenshot handler initialized, saving to '{self._dest}'")

    def _rotate_images(self) -> None:
        """Walk the current screenshot directory & ensure there are `n_screenshots-1` saved."""
        found_screenshots = []
        for name in os.listdir(self._dest):
            if name.startswith("screenshot_"):
                found_screenshots.append(name)

        found_screenshots.sort()
        print(f"Found {len(found_screenshots)} screenshots in '{self._dest}'")

        to_delete = []
        if len(found_screenshots) > (self.n_screenshots - 1):
            n_delete = len(found_screenshots) - self.n_screenshots + 1
            to_delete.extend(found_screenshots[:n_delete])

        print(f"Will delete {len(to_delete)} files")
        for name in to_delete:
            os.unlink(f"{self._dest}{name}")

    def take_screenshot(self) -> None:
        """
        Capture a screenshot of the current screen display & store to the SD.

        If `use_sd` is `False`, image is instead stored to onboard storage for quicker access. This
        should uaully only be used for debugging.

        NOTE: Screenshots are disambiguated using the device's local time, any existing file of the
        same name will be overwritten.
        """
        self._rotate_images()

        filename = f"screenshot_{dt.datetime.now().isoformat()}.bmp".replace(":", "_")
        print(self._log_str)
        save_pixels(f"{self._dest}{filename}")


class TouchscreenHandler:  # noqa: D101
    _touchscreen: adafruit_touchscreen.Touchscreen

    def __init__(self) -> None:
        self._touchscreen = adafruit_touchscreen.Touchscreen(
            x1_pin=board.TOUCH_XL,
            x2_pin=board.TOUCH_XR,
            y1_pin=board.TOUCH_YD,
            y2_pin=board.TOUCH_YU,
            calibration=((5200, 59000), (5800, 57000)),
            size=(SKYPORTAL_DISPLAY.width, SKYPORTAL_DISPLAY.height),
        )

        print("Touchscreen initialized")

    @property
    def touch_point(self) -> tuple[int, int, int] | None:  # noqa: D102
        return self._touchscreen.touch_point  # type: ignore[no-any-return]


class SkyPortalUI:  # noqa: D101
    main_display_group: displayio.Group
    aircraft_display_group: displayio.Group
    time_label_group: displayio.Group
    touch_label_group: displayio.Group

    time_label: label.Label
    touch_label: label.Label

    grid_bounds: tuple[float, float, float, float]

    screenshot_handler: ScreenshotHandler
    touchscreen_handler: TouchscreenHandler

    def __init__(self) -> None:
        # Set up main display element
        self.main_display_group = displayio.Group()
        self.aircraft_display_group = displayio.Group()
        self.time_label_group = displayio.Group()
        self.touch_label_group = displayio.Group()

        SKYPORTAL_DISPLAY.root_group = self.main_display_group
        self.build_splash()
        self.touchscreen_handler = TouchscreenHandler()
        self.screenshot_handler = ScreenshotHandler()

    def post_connect_init(self, grid_bounds: tuple[float, float, float, float]) -> None:
        """Execute initialization task(s)y that are dependent on an internet connection."""
        self.grid_bounds = grid_bounds
        self.set_base_map(grid_bounds=self.grid_bounds, use_default=True)

        # Not internet dependent, but dependent on the base map
        self.main_display_group.append(self.aircraft_display_group) # Put aircraft below labels
        self.add_time_label()
        self.add_touch_label()

    def build_splash(self) -> None:  # noqa: D102
        splash_display = displayio.Group()
        splash_img = displayio.OnDiskBitmap(SPLASH)
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
        self.main_display_group.append(splash_display)

    def set_base_map(
        self, grid_bounds: tuple[float, float, float, float], use_default: bool = False
    ) -> None:
        """
        Set the base map image on the PyPortal display.

        An attempt is made to query the Geoapify API for a map tile at the location specified by the
        specified mapping constants. If any part of this process fails, or if `use_default` is
        `True`, the device will fall back to loading the default map tile saved onboard.
        """
        if use_default:
            print("Skipping dynamic map tile generation, loading default")
            map_img = displayio.OnDiskBitmap(DEFAULT_BASE_MAP)
        else:
            map_img = get_base_map(grid_bounds=grid_bounds)

        map_group = displayio.Group()
        map_sprite = displayio.TileGrid(map_img, pixel_shader=map_img.pixel_shader)

        map_group.append(map_sprite)

        self.main_display_group.pop()  # Remove the splash screen
        self.main_display_group.append(map_group)

    def add_time_label(self) -> label.Label:
        """Add a label for the last update query time."""
        self.time_label = label.Label(
            anchor_point=(0, 0),
            anchored_position=(1, 0),
            font=terminalio.FONT,
            color=0x000000,
            background_color=0xFFFFFF,
            padding_top=2,
            padding_bottom=2,
            padding_left=2,
            padding_right=2,
            text="Waiting for OpenSky...",
        )

        self.time_label_group.append(self.time_label)
        self.main_display_group.append(self.time_label_group)

    def add_touch_label(self) -> label.Label:
        """Add a debug label for touchscreen status."""
        # Label for debugging, replace with an icon later
        self.touch_label = label.Label(
            anchor_point=(0, 1),
            anchored_position=(1, SKYPORTAL_DISPLAY.height),
            font=terminalio.FONT,
            color=0x000000,
            background_color=0xFFFFFF,
            padding_top=2,
            padding_bottom=2,
            padding_left=2,
            padding_right=2,
            text="Touchscreen Enabled",
        )

        self.touch_label_group.append(self.touch_label)
        self.main_display_group.append(self.touch_label_group)

    def draw_aircraft(
        self,
        aircraft: list[AircraftState],
        default_icon: AircraftIcon = BASE_ICON,
        custom_icons: dict[int, AircraftIcon] = AIRCRAFT_ICONS,
        skip_ground: bool = SKIP_GROUND,
        geo_altitude_threshold_m: float = GEO_ALTITUDE_THRESHOLD_M,
    ) -> None:
        """
        Clear the currently plotted aircraft icons & redraw from the provided list of aircraft.

        NOTE: Aircraft icons are not drawn if an aircraft's state vector is missing the required
        position & orientation data.
        """
        while len(self.aircraft_display_group):
            self.aircraft_display_group.pop()

        n_unplottable = 0
        n_ground = 0
        for ap in aircraft:
            if not ap.is_plottable():
                n_unplottable += 1
                continue

            if skip_ground and ap.on_ground:
                n_ground += 1
                continue

            if ap.geo_altitude_m is None or ap.geo_altitude_m < geo_altitude_threshold_m:
                n_ground += 1
                continue

            # If we've gotten here then lat/lon can't be None
            icon_x, icon_y = calculate_pixel_position(
                lat=ap.lat,  # type: ignore[arg-type]
                lon=ap.lon,  # type: ignore[arg-type]
                grid_bounds=self.grid_bounds,
            )

            icon_to_plot = custom_icons.get(ap.aircraft_category, default_icon)
            tile_index = int(ap.track / icon_to_plot.rotation_resolution_deg)  # type: ignore[operator]  # noqa: E501
            icon = displayio.TileGrid(
                bitmap=icon_to_plot.icon_sheet,
                pixel_shader=icon_to_plot.palette,
                tile_width=ICON_TILE_SIZE,
                tile_height=ICON_TILE_SIZE,
                default_tile=tile_index,
                x=icon_x,
                y=icon_y,
            )
            self.aircraft_display_group.append(icon)

        n_skipped = n_unplottable + n_ground
        print(
            f"Skipped drawing {n_skipped} aircraft ({n_unplottable} missing data, {n_ground} on ground)"  # noqa: E501
        )

    def touch_on(self) -> None:  # noqa: D102
        self.touch_label.text = "Touchscreen Enabled"

    def touch_off(self) -> None:  # noqa: D102
        self.touch_label.text = "Touchscreen Disabled"
