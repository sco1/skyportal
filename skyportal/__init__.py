import sys

import adafruit_requests as requests

__version__ = "2.1.0"
__url__ = "https://github.com/sco1/skyportal"

_impl = sys.implementation
USER_AGENT = (
    f"skyportal/{__version__} ({__url__}) "
    f"adafruit_requests/{requests.__version__} "
    f"{_impl.name}/{'.'.join(str(c) for c in _impl.version)} "
    f"{_impl._machine}"
)
