# Changelog
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`<major>`.`<minor>`.`<patch>`)

## [v2.1.0]
### Added
* #49 Add support for Flightradar24 API

### Changed
* Bump supported CircuitPython to v10.2 only
* Bump vendored libraries to v10.2 compatible `*.mpy` files
* Bump vendored `mpy-cross` binaries to CircuitPython v10.2
* #47 Update OpenSky API for new authentication flow
* Migrate from `settings.py` to `settings.toml` for secrets management

## [v2.0.0]
### Added
* #36 Add support for the FeatherS3 + TFT FeatherWing V2 w/TSC2007
* #24 Add map tile generation CLI helper utility, `map_gen`

### Changed
* Bump supported CircuitPython to v9.2.x only
* Bump vendored libraries to v9.2 compatible `*.mpy` files
* #36 (Internal) Refactor hardware interfaces into hardware-specific compatibility layers
* #28 Update vendored `mpy-cross` binaries to CircuitPython v9.2

## [v1.3.0]
### Changed
* #20 Bump supported CircuitPython to v9.x only
* #20 Update vendored libraries to v9.0 compatible `*.mpy` files

## [v1.2.0]
### Added
* #14 Add support for the ADSB.lol API
* #14 Add support for a generic flight data API

### Changed
* (Internal) Refactor API handlers to share a common base class

### Removed
* #11 Remove screenshot UI feature

## [v1.1.0]
### Added
* #3 Add optional screenshot UI target, enabled using the `SHOW_SCREENSHOT_BUTTON` config var
* #3 Add aircraft information popup on icon touch
* Add UI indicator to show when touch input is being blocked by a URL request
* #12 Add `USE_DEFAULT_MAP` config var to control whether or not to attempt to obtain the map tile from Geoapify

### Fixed
* #12 Fix map tile being hardcoded to using the default vs. querying Geoapify

### Changed
* (Internal) Refactor initialization flow to attempt to preserve memory early on for high-usage tasks

## [v1.0.0]
Initial release 🎉
