
# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0rc2]

### Added

- Added `solution.log` property.
- Added unit tests for `simulator.get_log` function and `solution.log` property
- Added __version__ definition 

### Fixed

- Fixed bug where `solution.status` was stuck on `queued` instead of `failed` when the solver failed.

### Changed

- Status update now returns status + most recent line from logs.
- Jupyter notebooks show output from `solution.log`.

### Removed

- 

## [1.0.0rc1]

First beta version.
