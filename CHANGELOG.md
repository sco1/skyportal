# Changelog
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`<major>`.`<minor>`.`<patch>`)

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
