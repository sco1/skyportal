import board
import displayio
import terminalio
from adafruit_display_text import label

from skyportal.aircraftlib import (
    AIRCRAFT_ICONS,
    AircraftIcon,
    AircraftState,
    BASE_ICON,
    ICON_TILE_SIZE,
)
from skyportal.maplib import calculate_pixel_position, get_base_map

SKYPORTAL_DISPLAY = board.DISPLAY

SPLASH = "./splash.bmp"
DEFAULT_BASE_MAP = "./default_map.bmp"


class SkyPortalUI:  # noqa: D101
    main_display_group: displayio.Group
    aircraft_display_group: displayio.Group
    time_label_group: displayio.Group

    time_label: label.Label

    grid_bounds: tuple[float, float, float, float]

    def __init__(self) -> None:
        # Set up main display element
        self.main_display_group = displayio.Group()
        self.aircraft_display_group = displayio.Group()
        self.time_label_group = displayio.Group()

        SKYPORTAL_DISPLAY.root_group = self.main_display_group
        self.build_splash()

    def post_connect_init(self, grid_bounds: tuple[float, float, float, float]) -> None:
        """Execute initialization task(s)y that are dependent on an internet connection."""
        self.grid_bounds = grid_bounds
        self.set_base_map(grid_bounds=self.grid_bounds, use_default=True)

        # Not internet dependent, but dependent on the base map
        self.add_time_label()
        self.main_display_group.append(self.aircraft_display_group)

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
            font=terminalio.FONT,
            color=0x000000,
            background_color=0xFFFFFF,
            anchor_point=(0, 0),
            anchored_position=(5, 5),
            padding_top=2,
            padding_bottom=2,
            padding_left=2,
            padding_right=2,
            text="Waiting for OpenSky...",
        )

        self.time_label_group.append(self.time_label)
        self.main_display_group.append(self.time_label_group)

    def draw_aircraft(
        self,
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
