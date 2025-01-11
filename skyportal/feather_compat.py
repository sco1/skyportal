import ssl
from collections import OrderedDict

import adafruit_requests
import socketpool
import wifi
from adafruit_featherwing import tft_featherwing_35
from adafruit_tsc2007 import TSC2007

from secrets import secrets
from skyportal.networklib import build_url, urlencode

# Time service API requires AIO username & API key from secrets
TIME_SERVICE = f"https://io.adafruit.com/api/v2/{secrets['aio_username']}/integrations/time/strftime"  # noqa: E501
TIME_SERVICE_FORMAT = r"%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"


class FeatherS3:
    def __init__(self, tz: str) -> None:
        self.tz = tz

        # Initialize display so we can see what's happening
        # This should also attempt to mount the SD card
        self._fw = tft_featherwing_35.TFTFeatherWing35V2()
        self.display = self._fw.display

        self.connect()

        ...  # Make sure the RTC is initialized here

        self.touchscreen = TouchscreenHandler(self._fw.touchscreen)

    @property
    def width(self) -> int:
        return self.display.width

    @property
    def height(self) -> int:
        return self.display.height

    def connect(self) -> None:
        wifi.radio.connect(secrets["ssid"], secrets["password"])
        print("Wifi connected")

        pool = socketpool.SocketPool(wifi.radio)
        self.session = adafruit_requests.Session(pool, ssl.create_default_context())

    def _set_rtc_from_timestr(self, timestr: str) -> None:
        raise NotImplementedError

    def get_local_time(self) -> str:
        adaIO_params = OrderedDict(
            [
                ("x-aio-key", secrets["aio_key"]),
                ("tz", self.tz),
                ("fmt", urlencode(TIME_SERVICE_FORMAT)),
            ]
        )
        query_url = build_url(TIME_SERVICE, adaIO_params)

        print(f"Querying local time for '{self.tz}'")
        resp = self.session.get(query_url)
        if resp.status_code != 200:
            raise RuntimeError("Error fetching local time from AIO")

        return resp.text

    @property
    def utc_offset(self) -> str:
        timestamp = self.get_local_time()
        return timestamp.split()[4]


class TouchscreenHandler:  # noqa: D101
    _is_pressed: bool

    def __init__(self, touchscreen: TSC2007) -> None:
        self._touchscreen = touchscreen

        self._is_pressed = False
        print("Touchscreen initialized")

    @property
    def touch_point(self) -> tuple[int, int, int] | None:
        """
        Helper layer to handle "debouncing" of touch screen inputs.

        An attempt is made to discard all touch inputs after the initial input until the finger is
        lifted from the screen. Due to the polling speed of the device, some inputs may still sneak
        through before the state change can be recognized.
        """
        if not self._touchscreen.touched:
            if self._is_pressed:
                self._is_pressed = False
            return None
        else:
            if self._is_pressed:
                return None
            else:
                self._is_pressed = True

                # Downstream consumers expecting a (x, y, pressure) tuple but the TSC2007 gives a
                # dictionary
                p = self._touchscreen.touch
                return (p["x"], p["y"], p["pressure"])
