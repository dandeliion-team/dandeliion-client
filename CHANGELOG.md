
# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0rc3]

### Added

- Added `solution.dump()` function to fetch all solution data and dump it into json file and `Simulator.restore()` function to restore solution (and reconnect with simulation)

### Fixed

-

### Changed

- final logs not stored client-side once fetched once to avoid unnecessary fetching
- Changed pinned version of Pybamm in pyproject.toml from 25.1.1 to 25.4.2

### Removed

-

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
