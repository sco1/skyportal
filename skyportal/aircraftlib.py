from __future__ import annotations

import adafruit_imageload
import displayio


class AircraftCategory:  # noqa: D101
    # OpenSky mapping
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

    # ADSB.lol mapping
    # Map these to match OpenSky since it was in the project first
    A0 = 1
    A1 = 2
    A2 = 3
    A3 = 4
    A4 = 5
    A5 = 6
    A6 = 7
    A7 = 8
    B0 = 1
    B1 = 9
    B2 = 10
    B3 = 11
    B4 = 12
    B5 = 13
    B6 = 14
    B7 = 15
    C0 = 1
    C1 = 16
    C2 = 17
    C3 = 18
    C4 = 19
    C5 = 20


class AircraftState:  # noqa: D101
    def __init__(
        self,
        icao: str,
        callsign: str | None,
        lat: float | None,
        lon: float | None,
        track: float | None,
        velocity_mps: float | None,
        on_ground: bool,
        baro_altitude_m: float | None,
        geo_altitude_m: float | None,
        vertical_rate_mps: float | None,
        aircraft_category: int,
    ) -> None:
        self.icao = icao
        self.callsign = callsign
        self.lat = lat
        self.lon = lon
        self.track = track
        self.velocity_mps = velocity_mps
        self.on_ground = on_ground
        self.baro_altitude_m = baro_altitude_m
        self.geo_altitude_m = geo_altitude_m
        self.vertical_rate_mps = vertical_rate_mps
        self.aircraft_category = aircraft_category

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

    @classmethod
    def from_opensky(cls, state_vector: dict) -> AircraftState:
        """
        Build an aircraft state from the provided OpenSky state vector.

        See: https://openskynetwork.github.io/opensky-api/rest.html#id4 for field descriptions
        """
        if state_vector[1] is not None:
            callsign = state_vector[1].strip()
            if not callsign:
                # Callsign can occasionally be an empty string, which we can treat as None
                callsign = None
        else:
            callsign = None

        return cls(
            icao=state_vector[0],
            callsign=callsign,
            lat=state_vector[6],
            lon=state_vector[5],
            track=state_vector[10],
            velocity_mps=state_vector[9],
            on_ground=state_vector[8],
            baro_altitude_m=state_vector[7],
            geo_altitude_m=state_vector[13],
            vertical_rate_mps=state_vector[11],
            aircraft_category=state_vector[17],
        )

    @classmethod
    def from_adsblol(cls, state_vector: dict) -> AircraftState:
        """
        Build an aircraft state from the provided ADSB.lol state vector.

        See: https://api.adsb.lol/docs for field schemas
        See: https://github.com/wiedehopf/readsb/blob/dev/README-json.md for ADSB field descriptions
        """
        if baro_alt := state_vector["alt_baro"] == "ground":
            baro_alt = None
            on_ground = True
        else:
            baro_alt *= 0.3048  # Provided in ft
            on_ground = False

        if (callsign := state_vector.get("flight", None)) is None:
            callsign = state_vector.get("r", None)

        # Ground track is likely not transmitted on the ground
        # If an aircraft is on the ground it may be transmitting true_heading
        if (track := state_vector.get("track", None)) is None:
            track = state_vector.get("true_heading", None)

        if (alt_geo := state_vector.get("alt_geo", None)) is not None:
            alt_geo *= 0.3048  # Provided in ft

        if (baro_rate := state_vector.get("baro_rate", None)) is not None:
            baro_rate *= 0.3048  # Provided in ft

        return cls(
            icao=state_vector["hex"],
            callsign=callsign,
            lat=state_vector["lat"],
            lon=state_vector["lon"],
            track=track,
            velocity_mps=state_vector["gs"] * 0.5144,  # Provided in kts
            on_ground=on_ground,
            baro_altitude_m=baro_alt,
            geo_altitude_m=alt_geo,
            vertical_rate_mps=baro_rate,
            aircraft_category=getattr(AircraftCategory, state_vector.get("category", "NO_INFO"), 0),
        )


class AircraftIcon:  # noqa: D101
    TILE_SIZE: int = 16

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


def load_aircraft_icons() -> tuple[AircraftIcon, dict[int, AircraftIcon]]:
    """Load & return aircraft icon sprite sheets."""
    default_icon = AircraftIcon.from_file("./assets/airplane_icons.bmp")
    extras = {
        AircraftCategory.ROTORCRAFT: AircraftIcon.from_file("./assets/heli_icons.bmp"),
    }

    return default_icon, extras
