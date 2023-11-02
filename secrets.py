# This file is where you keep secret settings, passwords, and tokens!
# If you put them in the code you risk committing that info or sharing it
# which would be not great. So, instead, keep it all in this one file and
# keep it a secret.

secrets = {
    # Your local timezone, see: http://worldtimeapi.org/timezones
    "timezone": "America/New_York",
    # WIFI information
    "ssid": "YOUR_SSID",
    "password": "YOUR_WIFI_PASSWORD",
    # Geoapify, used to generate static mapping
    "geoapify_key": "YOUR_GEOAPIFY_API_KEY",
    # Adafruit IO, used for transient image hosting
    "aio_username": "YOUR_AIO_USERNAME",
    "aio_key": "YOUR_AIO_KEY",
    # Open Sky Network credentials, for getting flight information
    "opensky_username": "YOUR_OPENSKY_USERNAME",
    "opensky_password": "YOUR_OPENSKY_PASSWORD",
}
