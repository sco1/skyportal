import adafruit_requests as requests
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_pyportal import PyPortal

try:
    from secrets import secrets
except ImportError as e:
    raise Exception("Could not locate secrets file.") from e

PYPORTAL = PyPortal()

# Main display element
SKYPORTAL_DISPLAY = board.DISPLAY
MAIN_DISPLAY_GROUP = displayio.Group()
SKYPORTAL_DISPLAY.root_group = MAIN_DISPLAY_GROUP


def build_splash() -> None:
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


# Initialization
build_splash()
PYPORTAL.network.connect()

# Main loop
while True:
    pass
