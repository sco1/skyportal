# skyportal
A PyPortal based flight tracker powered by [Adafruit](https://io.adafruit.com/), [Geoapify](https://www.geoapify.com/), and [The OpenSky Network](https://opensky-network.org/).

Heavily inspired by Bob Hammell"s PyPortal Flight Tracker ([GH](https://github.com/rhammell/pyportal-flight-tracker), [Tutorial](https://www.hackster.io/rhammell/pyportal-flight-tracker-0be6b0#story)).

Thank you to [markleoart](https://www.fiverr.com/markleoart) for creating the aircraft icon sprite sheets!

## Getting Started
Users are assumed have read through [Adafruit"s PyPortal learning guide](https://learn.adafruit.com/adafruit-pyportal). CircuitPython v8.2 is currently in use for this repository, no other versions are evaluated.

To get up and running, copy the following files to your PyPortal:

```
lib/
skyportal/
airplane_icons.bmp
boot.py
code.py
constants.py
default_map.bmp
heli_icons.bmp
pyportal_startup.bmp
pyportal_startup.wav
secrets.py
splash.bmp
```

**WARNING:** In order to generate the background map tile, this project's `boot.py` modifies the boot process to allow the filesystem to be used as a writeable cache. In the unlikely event that things go horribly awry you may lose the existing contents of your device, so be sure to back them up before working with this project.

### Secrets
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
