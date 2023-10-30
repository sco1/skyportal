from __future__ import annotations

import adafruit_imageload
import displayio


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
