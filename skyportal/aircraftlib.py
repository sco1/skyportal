from __future__ import annotations

import gc

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
    callsign: str | None
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
        # See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for field descriptions
        self.icao = state_vector[0]
        self.callsign = state_vector[1]
        self.lat = state_vector[6]
        self.lon = state_vector[5]
        self.track = state_vector[10]
        self.velocity_mps = state_vector[9]
        self.on_ground = state_vector[8]
        self.baro_altitude_m = state_vector[7]
        self.geo_altitude_m = state_vector[13]
        self.vertical_rate_mps = state_vector[11]
        self.aircraft_category = state_vector[17]

        if state_vector[1] is not None:
            self.callsign = state_vector[1].strip()

    def __str__(self) -> str:
        if self.callsign is not None:
            ac_id = self.callsign
        else:
            ac_id = self.icao

        if self.is_plottable():
            track_str = f"({self.lat:0.3f}, {self.lon:0.3f}), {int(self.track)}º"  # type: ignore[arg-type]  # noqa: E501
        else:
            track_str = "No track information"

        if self.geo_altitude_m is not None:
            track_str = f"{track_str} @ {int(self.geo_altitude_m)}m MSL"

        return f"{ac_id}: {track_str}"

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


# Current icon tiles are made using primary colors #ffff00 (yellow) and #25FF00 (green, background)
ICON_TILE_SIZE = 16
BASE_ICON = AircraftIcon.from_file("./assets/airplane_icons.bmp")
AIRCRAFT_ICONS = {
    AircraftCategory.ROTORCRAFT: AircraftIcon.from_file("./assets/heli_icons.bmp"),
}
gc.collect()
