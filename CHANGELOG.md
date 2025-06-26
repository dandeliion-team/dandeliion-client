
# Changelog

All notable changes to this project will be documented in this file.


# [1.0.2]

### Added

- security policy (SECURITY.md)

### Fixed

- permission for docs github action
- time column fetching (correct log output)

### Changed

- LICENSE file


## [1.0.1]

### Fixed

- time column getting fetched when needed
- proper error message when incomplete solution restored without connection details
- dead-lock fixed when joining on incomplete simulation without correct connection details

### Changed

- API url now stored in internal data as well and used for reconnecting restored simulations


## [1.0.0]

### Added

- Added `solution.dump()` function to fetch all solution data and dump it into json file and `Simulator.restore()` function to restore solution (and reconnect with simulation)
- `join()` function for solutions to wait for solutions to be ready (in non-blocking mode)
- Changelog checker added to github workflow

### Fixed

- custom error messages from server now passed on correctly (and shown as part of messages of thrown Exceptions)

### Changed

- final logs not stored client-side once fetched once to avoid unnecessary fetching
- Changed pinned version of Pybamm in pyproject.toml from 25.1.1 to 25.4.2


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


## [1.0.0rc1]

First beta version.
