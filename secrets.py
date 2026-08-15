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
    # Open Sky Network credentials
    # Can be omitted if not using OpenSky
    "opensky_id": "YOUR_OPENSKY_CLIENT_ID",
    "opensky_secret": "YOUR_OPENSKY_SECRET",
    # Flightradar24 credentials
    # Can be omitted if not using Flightradar24
    "fr24_token": "YOUR_FR24_TOKEN",
    # Proxy API Gateway credentials
    # Can be omitted if not using a proxy server
    "proxy_api_url": "YOUR_PROXY_API_URL",
    "proxy_api_key": "YOUR_PROXY_API_KEY",
}
