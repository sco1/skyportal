# Changelog
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`<major>`.`<minor>`.`<patch>`)

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
