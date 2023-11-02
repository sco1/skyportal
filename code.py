from __future__ import annotations

import math
import time

import adafruit_datetime as dt
from adafruit_pyportal import PyPortal

from skyportal.displaylib import SkyPortalUI
from skyportal.maplib import build_bounding_box
from skyportal.opensky import APIException, APITimeoutError, OpenSky

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e


def _utc_to_local(utc_timestamp: int, utc_offset: str = "-0000") -> dt.datetime:
    """
    Convert the given timestamp into local time with the provided UTC offset.

    UTC offset is assumed to be provided as `"±HHMM"`.
    """
    hours = int(utc_offset[:3])
    minutes = math.copysign(int(utc_offset[-2:]), hours)
    delta = dt.timedelta(hours=hours, minutes=minutes)

    utc_time = dt.datetime.fromtimestamp(utc_timestamp)
    return utc_time + delta


# Initialization
PYPORTAL = PyPortal()  # This also takes care of mounting the SD to /sd
skyportal_ui = SkyPortalUI()

PYPORTAL.network.connect()
print("Wifi connected")

# The internal PyPortal query to AIO returns as "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
# This method sets the internal clock, but we also retain it to transform the API time to local
init_timestamp = PYPORTAL.get_local_time(location=secrets["timezone"])
utc_offset = init_timestamp.split()[4]

grid_bounds = build_bounding_box()
skyportal_ui.post_connect_init(grid_bounds)
opensky_handler = OpenSky(grid_bounds=grid_bounds)

print(f"\n{'='*40}\nInitialization complete\n{'='*40}\n")

# Main loop
while True:
    try:
        opensky_handler.update()
    except APITimeoutError:
        print("Request to OpenSky timed out")
    except APIException as e:
        print(e)

    if opensky_handler.can_draw():
        print("Updating aircraft locations")
        skyportal_ui.draw_aircraft(opensky_handler.aircraft)
        skyportal_ui.time_label.text = f"{_utc_to_local(opensky_handler.api_time, utc_offset)}"
    else:
        print("No aircraft to draw, skipping redraw")

    next_request_at = dt.datetime.now() + dt.timedelta(seconds=opensky_handler.refresh_interval)
    print(f"Sleeping... next refresh at {next_request_at} local")
    time.sleep(opensky_handler.refresh_interval)
