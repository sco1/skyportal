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


def set_base_map() -> None:
    """"""
    map_group = displayio.Group()
    map_img = displayio.OnDiskBitmap("./default_map.bmp")
    map_sprite = displayio.TileGrid(map_img, pixel_shader=map_img.pixel_shader)

    map_group.append(map_sprite)

    MAIN_DISPLAY_GROUP.pop()  # Remove the splash screen
    MAIN_DISPLAY_GROUP.append(map_group)


# Initialization
build_splash()
PYPORTAL.network.connect()
set_base_map()

# Main loop
while True:
    pass
