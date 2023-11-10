# skyportal
A PyPortal based flight tracker powered by [Adafruit](https://io.adafruit.com/), [Geoapify](https://www.geoapify.com/), and [The OpenSky Network](https://opensky-network.org/).

Heavily inspired by Bob Hammell"s PyPortal Flight Tracker ([GH](https://github.com/rhammell/pyportal-flight-tracker), [Tutorial](https://www.hackster.io/rhammell/pyportal-flight-tracker-0be6b0#story)).

Thank you to [markleoart](https://www.fiverr.com/markleoart) for creating the aircraft icon sprite sheets!

![screenshot](./doc/screenie.bmp "SkyPortal in action")

## Getting Started
Users are assumed have read through [Adafruit's PyPortal learning guide](https://learn.adafruit.com/adafruit-pyportal). CircuitPython v8.2 is currently in use for this repository, no other versions are evaluated.

The CircuitPython libraries in `lib` are sourced from the Official and Community bundles, which can be found on the [CircuitPython libraries page](https://learn.adafruit.com/adafruit-pyportal)

**WARNING:** In order to generate the background map tile, this project's `boot.py` modifies the boot process to allow the filesystem to be used as a writeable cache. In the unlikely event that things go horribly awry you may lose the existing contents of your device, so be sure to back them up before working with this project.

### Installation
#### From Source
To get up and running, copy the following files from the repository to your PyPortal:

```
assets/
lib/
skyportal/
boot.py
code.py
pyportal_startup.bmp
pyportal_startup.wav
secrets.py
skyportal_config.py
```

#### From GH Release
The Skyportal [Releases page](https://github.com/sco1/skyportal/releases) contains bundled `*.tar.gz` archives, built in CI, that can be downloaded and extracted directly onto the device. Bundles come in two flavors: one pure-python implementation and a compiled version, where the `skyportal` library has been [compiled to `*.mpy`](https://learn.adafruit.com/welcome-to-circuitpython/library-file-types-and-frozen-libraries#dot-mpy-library-files-3117643) and added to `lib/`.

### Configuration
#### Secrets
The following secrets are required for functionality:

```py
secrets = {
    # Your local timezone, see: http://worldtimeapi.org/timezones
    "timezone": "America/New_York",
    # WIFI information
    "ssid": "YOUR_SSID",
    "password": "YOUR_WIFI_PASSWORD",
    # Geoapify, used to generate static mapping
    "geoapify_key": "YOUR_GEOAPIFY_API_KEY",
    # Adafruit IO, used for transient image hosting & local time lookup
    "aio_username" : "YOUR_AIO_USERNAME",
    "aio_key" : "YOUR_AIO_KEY",
    # Open Sky Network credentials, for getting flight information
    "opensky_username": "YOUR_OPENSKY_USERNAME",
    "opensky_password": "YOUR_OPENSKY_PASSWORD"
}
```

#### Skyportal Configuration
A collection of functionality-related constants is specified in `skyportal_config.py`, which can be adjusted to suit your needs:

| Variable Name              | Description                                           | Default  |
|----------------------------|-------------------------------------------------------|----------|
| `SHOW_SCREENSHOT_BUTTON`   | Provide a UI button for taking screenshots            | `True`   |
| `KEEP_N_SCREENSHOTS`       | Keep the `n` most recent screenshots in SD storage    | `3`      |
| `MAP_CENTER_LAT`           | Map center latitude, decimal degrees                  | `42.41`  |
| `MAP_CENTER_LON`           | Map center longitude, deimal degrees                  | `-71.17` |
| `GRID_WIDTH_MI`            | Map grid width, miles                                 | `15`     |
| `SKIP_GROUND`              | Skip drawing aircraft on the ground                   | `True`   |
| `GEO_ALTITUDE_THRESHOLD_M` | Skip drawing aircraft below this GPS altitude, meters | `20`     |

## Touchscreen Functionality
**NOTE:** Due to the lack of an available asynchronous requests library for CircuitPython, the call to the OpenSky API is blocking and will block touchscreen functionality until a response is obtained. An attempt is made to reflect the current blocking status in all UI elements, indicating to the user that their touch inputs can't be processed.

### Aircraft Information
Tapping on an aircraft icon will display state information for the aircraft closest to the registered touch point.

### Screenshot
If enabled in the SkyPortal configuration file, a screenshot button is created in the lower left, allowing the user to take a screenshot to SD card storage. The device utilizes a rolling storage, keeping the `n` most recent screenshots and discarding the oldest screenshot if above this threshold.
