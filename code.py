from __future__ import annotations

import gc
import math

from adafruit_datetime import datetime, timedelta
from adafruit_pyportal import PyPortal

from skyportal.displaylib import SkyPortalUI
from skyportal.maplib import build_bounding_box
from skyportal.networklib import APIException, APITimeoutError

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

try:
    import skyportal_config
except ImportError as e:
    raise Exception("Could not locate configuration file.") from e


def _utc_to_local(utc_timestamp: int, utc_offset: str = "-0000") -> datetime:
    """
    Convert the given timestamp into local time with the provided UTC offset.

    UTC offset is assumed to be provided as `"±HHMM"`.
    """
    hours = int(utc_offset[:3])
    minutes = math.copysign(int(utc_offset[-2:]), hours)
    delta = timedelta(hours=hours, minutes=minutes)

    utc_time = datetime.fromtimestamp(utc_timestamp)
    return utc_time + delta


# Device Initialization
PYPORTAL = PyPortal()  # This also takes care of mounting the SD to /sd
skyportal_ui = SkyPortalUI(enable_screenshot=skyportal_config.SHOW_SCREENSHOT_BUTTON)

PYPORTAL.network.connect()
print("Wifi connected")

# The internal PyPortal query to AIO returns as "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
# This method sets the internal clock, but we also retain it to transform the API time to local
init_timestamp = PYPORTAL.get_local_time(location=secrets["timezone"])
utc_offset = init_timestamp.split()[4]

grid_bounds = build_bounding_box()
skyportal_ui.post_connect_init(grid_bounds)

if skyportal_config.AIRCRAFT_DATA_SOURCE == "adsblol":
    from skyportal.adsblol import AdsbLol

    api_handler = AdsbLol(
        lat=skyportal_config.MAP_CENTER_LAT,
        lon=skyportal_config.MAP_CENTER_LON,
        radius=skyportal_config.GRID_WIDTH_MI * 2,
    )
    print("Using ADSB.lol as aircraft data source")
elif skyportal_config.AIRCRAFT_DATA_SOURCE == "opensky":
    from skyportal.opensky import OpenSky

    api_handler = OpenSky(grid_bounds=grid_bounds)
    print("Using OpenSky as aircraft data source")
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
        except (APITimeoutError, APIException) as e:
            print(e)

        gc.collect()

        if api_handler.can_draw:
            print("Updating aircraft locations")
            skyportal_ui.draw_aircraft(api_handler.aircraft)
            skyportal_ui.time_label.text = f"{_utc_to_local(api_handler.api_time, utc_offset)}"
        else:
            print("No aircraft to draw, skipping redraw")

        loop_start_time = datetime.now()
        next_request_at = loop_start_time + api_handler.refresh_interval
        print(f"Sleeping... next refresh at {next_request_at} local")
        skyportal_ui.touch_on()

    p = skyportal_ui.touchscreen_handler.touch_point
    if p:
        skyportal_ui.process_touch(p)
