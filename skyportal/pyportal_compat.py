import adafruit_touchscreen
import board
from adafruit_pyportal import PyPortal as AdaPyPortal


class PyPortal:
    """
    Hardware compatibility layer for the Adafruit PyPortal.

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
        Initialize the PyPortal.

        The provided `tz` string is assumed to originate from the device's secrets & is used to
        provide location information for timestamp queries to AIO.

        On initialization:
            * Initialize the device, which should also attempt to mount the SD card
            * Initialize the WiFi connection to the configured network & create a request session
                * The PyPortal's internal method also sets the device's internal clock
            * Initialize the touchscreen handler
        """
        self.tz = tz
        self.device = AdaPyPortal()  # This also takes care of mounting the SD to /sd

        self.device.network.connect()
        print("Wifi connected")

        self.session = self.device.network._wifi.requests

        self.display = board.DISPLAY
        self.touchscreen = TouchscreenHandler(screen_width=self.width, screen_height=self.height)

    @property
    def width(self) -> int:  # noqa: D102
        return self.display.display.width  # type: ignore[no-any-return]

    @property
    def height(self) -> int:  # noqa: D102
        return self.display.display.height  # type: ignore[no-any-return]

    def get_local_time(self) -> str:
        """
        Query AIO for the current local timestamp.

        The query to AIO returns as `"%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"`. See: https://strftime.org/
        for field details.

        NOTE: This utlizies the PyPortal's native `get_local_time` method, which also sets the
        device's internal clock using the returned timestamp.
        """
        # The internal PyPortal query to AIO returns as "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
        # The internal method also sets the internal clock
        return self.device.get_local_time(location=self.tz)  # type: ignore[no-any-return]

    @property
    def utc_offset(self) -> str:
        """Query AIO for the local UTC offset based on the configured TZ."""
        # The query to AIO returns as "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
        timestamp = self.get_local_time()
        return timestamp.split()[4]


class TouchscreenHandler:  # noqa: D101
    _touchscreen: adafruit_touchscreen.Touchscreen

    _is_pressed: bool

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self._touchscreen = adafruit_touchscreen.Touchscreen(
            x1_pin=board.TOUCH_XL,
            x2_pin=board.TOUCH_XR,
            y1_pin=board.TOUCH_YD,
            y2_pin=board.TOUCH_YU,
            calibration=((5200, 59000), (5800, 57000)),
            size=(screen_width, screen_height),
        )
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
        if self._touchscreen.touch_point is None:
            if self._is_pressed:
                self._is_pressed = False
            return None
        else:
            if self._is_pressed:
                return None
            else:
                self._is_pressed = True
                return self._touchscreen.touch_point  # type: ignore[no-any-return]
