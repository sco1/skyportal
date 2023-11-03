import os

import adafruit_datetime as dt
import adafruit_touchscreen
import board
import displayio
import terminalio
from adafruit_bitmapsaver import save_pixels
from adafruit_display_text import label

from skyportal.aircraftlib import (
    AIRCRAFT_ICONS,
    AircraftIcon,
    AircraftState,
    BASE_ICON,
    ICON_TILE_SIZE,
)
from skyportal.maplib import calculate_pixel_position, get_base_map
from skyportal_config import GEO_ALTITUDE_THRESHOLD_M, KEEP_N_SCREENSHOTS, SKIP_GROUND

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass


SKYPORTAL_DISPLAY = board.DISPLAY

SPLASH = "./assets/splash.bmp"
DEFAULT_BASE_MAP = "./assets/default_map.bmp"
SCREENSHOT_ENABLED = "./assets/camera_green.bmp"
SCREENSHOT_DISABLED = "./assets/camera_red.bmp"


class ScreenshotHandler:
    """Handle screenshot saving rotation, saving up to a maximum of `n_screenshots` per location."""

    n_screenshots: int
    _dest: str
    _log_str: str

    def __init__(self, n_screenshots: int = KEEP_N_SCREENSHOTS, use_sd: bool = True):
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

        to_delete = []
        if len(found_screenshots) > (self.n_screenshots - 1):
            n_delete = len(found_screenshots) - self.n_screenshots + 1
            to_delete.extend(found_screenshots[:n_delete])

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


class ImageButton:
    """
    Helper object for initializing a BMP image as a touchscreen button.

    A callback function can be provided to dispatch actions when the button is pressed. Callback
    functions are assumed to take no arguments, and any returns are ignored.
    """

    tilegrid: displayio.TileGrid

    _x_bounds: range
    _y_bounds: range

    callback: t.Optional[t.Callable]

    def __init__(
        self, img_filepath: str, x: int = 0, y: int = 0, callback: t.Optional[t.Callable] = None
    ) -> None:
        img = displayio.OnDiskBitmap(img_filepath)

        self._x_bounds = range(x, x + img.width + 1)
        self._y_bounds = range(y, y + img.height + 1)

        self.tilegrid = displayio.TileGrid(img, pixel_shader=img.pixel_shader, x=x, y=y)

        self.callback = callback

    def _contains(self, touch_coord: tuple[int, int, int]) -> bool:
        query_x, query_y, _ = touch_coord

        return (query_x in self._x_bounds) and (query_y in self._y_bounds)

    def check_fire(self, touch_coord: tuple[int, int, int]) -> None:
        """Check if the touch input is within the button's bounds & fire the callback if it is."""
        if self.callback is not None and self._contains(touch_coord):
            self.callback()

    def show(self, state: bool = True) -> None:  # noqa: D102
        self.tilegrid.hidden = state


class SkyPortalUI:  # noqa: D101
    main_display_group: displayio.Group
    aircraft_display_group: displayio.Group
    time_label_group: displayio.Group
    screenshot_button_group: displayio.Group

    time_label: label.Label

    screenshot_buttons: dict[bool, ImageButton]

    screenshot_handler: ScreenshotHandler
    touchscreen_handler: TouchscreenHandler

    grid_bounds: tuple[float, float, float, float]

    def __init__(self, enable_screenshot: bool = False) -> None:
        # Set up main display element
        self.main_display_group = displayio.Group()
        self.aircraft_display_group = displayio.Group()
        self.time_label_group = displayio.Group()
        self.screenshot_button_group = displayio.Group()

        SKYPORTAL_DISPLAY.root_group = self.main_display_group
        self.build_splash()
        self.touchscreen_handler = TouchscreenHandler()
        self.screenshot_handler = ScreenshotHandler()

        self._enable_screenshot = enable_screenshot

    def post_connect_init(self, grid_bounds: tuple[float, float, float, float]) -> None:
        """Execute initialization task(s)y that are dependent on an internet connection."""
        self.grid_bounds = grid_bounds
        self.set_base_map(grid_bounds=self.grid_bounds, use_default=True)

        # Not internet dependent, but dependent on the base map
        # Put aircraft below all other UI elements
        self.main_display_group.append(self.aircraft_display_group)
        self.add_time_label()

        if self._enable_screenshot:
            self.add_screenshot_buttons()

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

    def add_time_label(self) -> None:  # noqa: D102
        self.time_label = label.Label(
            anchor_point=(0, 0),
            anchored_position=(2, 0),
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

    def add_screenshot_buttons(self) -> None:  # noqa: D102
        screenshot_enabled = ImageButton(
            SCREENSHOT_ENABLED,
            y=(SKYPORTAL_DISPLAY.height - 40),
            callback=self.screenshot_handler.take_screenshot,
        )
        screenshot_disabled = ImageButton(SCREENSHOT_DISABLED, y=(SKYPORTAL_DISPLAY.height - 40))
        screenshot_disabled.show(False)

        self.screenshot_buttons = {True: screenshot_enabled, False: screenshot_disabled}

        self.screenshot_button_group.append(screenshot_disabled.tilegrid)
        self.screenshot_button_group.append(screenshot_enabled.tilegrid)
        self.main_display_group.append(self.screenshot_button_group)

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
        self.screenshot_buttons[True].tilegrid.hidden = False
        self.screenshot_buttons[False].tilegrid.hidden = True

    def touch_off(self) -> None:  # noqa: D102
        self.screenshot_buttons[True].tilegrid.hidden = True
        self.screenshot_buttons[False].tilegrid.hidden = False

    def process_touch(self, touch_coord: tuple[int, int, int]) -> None:
        """Process the provided touch input coordinate & fire the first action required."""
        if self._enable_screenshot:
            self.screenshot_buttons[True].check_fire(touch_coord)
