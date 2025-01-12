import ssl
import time
from collections import OrderedDict

import adafruit_requests
import rtc
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
    """
    Hardware compatibility layer for the Feather S3 + FeatherWing.

    This layer currently targets the FeatherS3 - ESP32-S3 development board by Unexpected Maker,
    paired with the 3.5" Adafruit TFT FeatherWing - V2 w/TSC2007.

    The hardware compatibility layer makes available for downstream:
        * A `connect` method for connecting to wifi & initializing a request session
        * A `session` attribute to use for web requests
        * A `display` attribute, allowing access to the screen's `root_display` for rendering
        * A `touchscreen` attribute, exposing the device-specific touchscreen handler
        * A `get_local_time` method to query AIO for the current local timestamp
        * A `utc_offset` property to fetch the local UTC offset from AIO
        * `width` & `height` pixel screen size properties
    """

    def __init__(self, tz: str) -> None:
        """
        Initialize the FeatherS3 + TFT FeatherWing V2 w/TSC2007.

        The provided `tz` string is assumed to originate from the device's secrets & is used to
        provide location information for timestamp queries to AIO.

        On initialization:
            * Initialize the touchscreen display, which should also attempt to mount the SD card
            * Initialize the WiFi connection to the configured network & create a request session
            * Initialize the internal clock to the local time provided by AIO
            * Initialize the touchscreen handler
        """
        self.tz = tz
        self.connect()

        # I'm not sure why at the moment, but setting the RTC needs to be before the display is
        # initialized otherwise it gets stuck on a white screen
        self._set_rtc_from_timestr(self.get_local_time())

        # This should also attempt to mount the SD card
        self._fw = tft_featherwing_35.TFTFeatherWing35V2()
        self.display = self._fw.display

        self.touchscreen = TouchscreenHandler(self._fw.touchscreen)

    @property
    def width(self) -> int:  # noqa: D102
        return self.display.width  # type: ignore[no-any-return]

    @property
    def height(self) -> int:  # noqa: D102
        return self.display.height  # type: ignore[no-any-return]

    def connect(self) -> None:
        """Connect to the WiFi network specified `secrets` & initialize a request session."""
        wifi.radio.connect(secrets["ssid"], secrets["password"])
        print("Wifi connected")

        pool = socketpool.SocketPool(wifi.radio)
        self.session = adafruit_requests.Session(pool, ssl.create_default_context())

    def _set_rtc_from_timestr(self, timestr: str) -> None:
        """
        Set the local device time using the provided timestamp from AIO.

        The provided timestamp is assumed to be of the form `"%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"`.
        """
        comps = timestr.split()

        year, month, day = (int(n) for n in comps[0].split("-"))
        year_day, week_day = int(comps[2]), int(comps[3])

        time_str = comps[1].split(".")[0]  # Remove decimal seconds component
        hour, minute, second = (int(n) for n in time_str.split(":"))

        is_dst = -1  # Don't know this from the string, usually will get filled in correctly

        now = time.struct_time((year, month, day, hour, minute, second, week_day, year_day, is_dst))

        r = rtc.RTC()
        r.datetime = now
        print(f"Initialized RTC to {timestr}")

    def get_local_time(self) -> str:
        """
        Query AIO for the current local timestamp.

        The query to AIO returns as `"%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"`. See: https://strftime.org/
        for field details.
        """
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

        return resp.text  # type: ignore[no-any-return]

    @property
    def utc_offset(self) -> str:
        """Query AIO for the local UTC offset based on the configured TZ."""
        # The query to AIO returns as "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
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
