from __future__ import annotations

import gc
import math
import os
import sys

from adafruit_datetime import datetime, timedelta

from skyportal.displaylib import SkyPortalUI
from skyportal.maplib import build_bounding_box
from skyportal.networklib import APIExceptionError, APIHandlerBase, APITimeoutError

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

try:
    import skyportal_config
except ImportError as e:
    raise Exception("Could not locate configuration file.") from e


def _utc_to_local(utc_timestamp: float, utc_offset: str = "-0000") -> datetime:
    """
    Convert the given timestamp into local time with the provided UTC offset.

    UTC offset is assumed to be provided as `"±HHMM"`.
    """
    hours = int(utc_offset[:3])
    minutes = math.copysign(int(utc_offset[-2:]), hours)
    delta = timedelta(hours=hours, minutes=minutes)

    utc_time = datetime.fromtimestamp(utc_timestamp)
    return utc_time + delta


# Starting with CircuitPython v9.0 an "sd" folder has to be created to be used as a mount point
# For newer installs this should already be present but may not if migrating from v8.x
# See: https://github.com/adafruit/circuitpython/issues/8872
# See: https://github.com/adafruit/circuitpython/pull/8860
if "sd" not in os.listdir("/"):
    # Our boot.py already makes the filesystem writeable so we shouldn't need to guard
    os.mkdir("/sd")

# Device Initialization
# Written verbosely for now, once initial functionality is achieved then we can look at abstracting
# away into the hardware handlers
impl = sys.implementation
if "PyPortal" in impl._machine:
    print("Initializing PyPortal")
    from skyportal.pyportal_compat import PyPortal

    device = PyPortal(tz=secrets["timezone"])
elif "FeatherS3" in impl._machine:
    print("Initializing FeatherS3")
    from skyportal.feather_compat import FeatherS3

    device = FeatherS3(tz=secrets["timezone"])
else:
    raise RuntimeError("Unknown machine type: '{impl._machine}'")

skyportal_ui = SkyPortalUI(device)
grid_bounds = build_bounding_box(screen_width=device.width, screen_height=device.height)
skyportal_ui.post_connect_init(grid_bounds)

api_handler: APIHandlerBase
if skyportal_config.AIRCRAFT_DATA_SOURCE == "adsblol":
    from skyportal.networklib import ADSBLol

    api_handler = ADSBLol(
        request_session=device.session,
        lat=skyportal_config.MAP_CENTER_LAT,
        lon=skyportal_config.MAP_CENTER_LON,
        radius=skyportal_config.GRID_WIDTH_MI * 2,
    )
    print("Using ADSB.lol as aircraft data source")
elif skyportal_config.AIRCRAFT_DATA_SOURCE == "opensky":
    from skyportal.networklib import OpenSky

    api_handler = OpenSky(request_session=device.session, grid_bounds=grid_bounds)
    print("Using OpenSky as aircraft data source")
elif skyportal_config.AIRCRAFT_DATA_SOURCE == "proxy":
    from skyportal.networklib import ProxyAPI

    api_handler = ProxyAPI(
        request_session=device.session,
        lat=skyportal_config.MAP_CENTER_LAT,
        lon=skyportal_config.MAP_CENTER_LON,
        radius=skyportal_config.GRID_WIDTH_MI * 2,
    )
    print("Using proxy API as aircraft data source")
else:
    raise ValueError(f"Unknown API specified: '{skyportal_config.AIRCRAFT_DATA_SOURCE}'")

gc.collect()
print(f"\n{'='*40}\nInitialization complete\n{'='*40}\n")

# Main loop
skyportal_ui.touch_on()
loop_start_time = datetime.now() - api_handler.refresh_interval  # Force first API call
while True:
    if (datetime.now() - loop_start_time) >= api_handler.refresh_interval:
        skyportal_ui.touch_off()
        try:
            api_handler.update()
        except (APITimeoutError, APIExceptionError) as e:
            print(e)

        gc.collect()

        if api_handler.can_draw:
            print("Updating aircraft locations")
            skyportal_ui.draw_aircraft(api_handler.aircraft)

            local_time_str = _utc_to_local(api_handler.api_time, device.utc_offset)
            skyportal_ui.time_label.text = f"{local_time_str}"
        else:
            print("No aircraft to draw, skipping redraw")

        loop_start_time = datetime.now()
        next_request_at = loop_start_time + api_handler.refresh_interval
        print(f"Sleeping... next refresh at {next_request_at} local")
        skyportal_ui.touch_on()

    p = skyportal_ui.touchscreen_handler.touch_point
    if p:
        skyportal_ui.process_touch(p)
