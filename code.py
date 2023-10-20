from collections import OrderedDict

import adafruit_requests as requests
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_pyportal import PyPortal

# CircuitPython doesn't have the typing module, so throw this away at runtime
try:
    import typing as t
except ImportError:
    pass

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

# Mapping constants
# If adjusting the centerpoint/zoom, use an image size of 2x the PyPortal dimensions in order to
# shink some of the labels in the resulting image
GEOAPIFY_API_URL_BASE = "https://maps.geoapify.com/v1/staticmap"
MAP_CENTER_LAT = 42.458874
MAP_CENTER_LON = -71.021154
MAP_ZOOM = 9
MAP_STYLE = "klokantech-basic"

AIO_URL_BASE = f"https://io.adafruit.com/api/v2/{secrets['aio_username']}/integrations/image-formatter"  # noqa: E501

PYPORTAL = PyPortal()

# Main display element
SKYPORTAL_DISPLAY = board.DISPLAY
MAIN_DISPLAY_GROUP = displayio.Group()
SKYPORTAL_DISPLAY.root_group = MAIN_DISPLAY_GROUP


def build_splash() -> None:  # noqa: D103
    splash_display = displayio.Group()
    splash_img = displayio.OnDiskBitmap("/splash.bmp")
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
    MAIN_DISPLAY_GROUP.append(splash_display)


def build_url(base: str, params: dict[str, t.Any]) -> str:
    """Build a url from the provided base & parameter(s)."""
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{param_str}"


def urlencode(url: str) -> str:
    """Encode any non-alphanumeric, non-digit, or chars that aren't `-` or `.` in the given URL."""
    encoded_chars = []
    for c in url:
        if any((c.isalpha(), c.isdigit(), (c in ("-", ".")))):
            encoded_chars.append(c)
        else:
            encoded_chars.append(f"%{ord(c):02X}")

    return "".join(encoded_chars)


def set_base_map(use_default: bool = False) -> None:
    """
    Set the base map image on the PyPortal display.

    An attempt is made to query the Geoapify API for a map tile at the location specified by the
    module-level map constants. Since Geoapify returns a PNG & PyPortal needs a BMP, this image is
    sent to Adafruit IO for resizing & conversion.

    NOTE: The request sent to Geoapify specifies an image size 2x that of the PyPortal display to
    shrink down the labels on the final image for better visualization.

    If any part of this process fails, or if `use_default` is `True`, the device will fall back to
    loading the default map tile saved onboard.
    """
    map_params = OrderedDict(
        [
            ("apiKey", secrets["geoapify_key"]),
            ("style", MAP_STYLE),
            ("format", "png"),
            ("center", f"lonlat:{MAP_CENTER_LON},{MAP_CENTER_LAT}"),
            ("zoom", MAP_ZOOM),
            ("width", SKYPORTAL_DISPLAY.width * 2),
            ("height", SKYPORTAL_DISPLAY.height * 2),
        ]
    )
    map_query_url = build_url(GEOAPIFY_API_URL_BASE, map_params)

    adaIO_params = OrderedDict(
        [
            ("x-aio-key", secrets["aio_key"]),
            ("width", SKYPORTAL_DISPLAY.width),
            ("height", SKYPORTAL_DISPLAY.height),
            ("output", "BMP16"),
            ("url", urlencode(map_query_url)),  # Encode so AdaIO doesn't eat the Geoapify params
        ]
    )
    adaIO_query_url = build_url(AIO_URL_BASE, adaIO_params)

    if use_default:
        print("Skipping dynamic map tile generation")
        map_img = displayio.OnDiskBitmap("./default_map.bmp")
    else:
        try:
            print("Requesting map tile from Geoapify via AdaIO")
            r = requests.get(adaIO_query_url)
            if r.status_code != 200:
                raise RuntimeError(f"Bad response received from AdaIO: {r.status_code}, {r.text}")

            with open("./generated_map.bmp", "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    f.write(chunk)

            map_img = displayio.OnDiskBitmap("./generated_map.bmp")
            print("Geoapify map tile successfully generated")
        except Exception as e:
            print("Failed to download map:", e)
            print("Falling back to default tile")
            map_img = displayio.OnDiskBitmap("./default_map.bmp")

    map_group = displayio.Group()
    map_sprite = displayio.TileGrid(map_img, pixel_shader=map_img.pixel_shader)

    map_group.append(map_sprite)

    MAIN_DISPLAY_GROUP.pop()  # Remove the splash screen
    MAIN_DISPLAY_GROUP.append(map_group)


# Initialization
build_splash()
PYPORTAL.network.connect()
set_base_map(use_default=True)

# Main loop
while True:
    pass
