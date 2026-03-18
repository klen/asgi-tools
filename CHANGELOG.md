# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [2.0.1] - 2026-03-18

### Changed

- Updated multipart form handling:
  `request.form()` now relies on `max_size` as the single size control.
- Removed the separate `file_memory_limit` argument from form parsing APIs.
- Tightened typing in `Request` internals and method signatures.

### Fixed

- Refreshed project/tooling configuration and compatibility checks.

## [1.4.0] - 2025-11-06

### Added

- Python 3.14 support.

### Changed

- Tooling and docs updates for the 3.14 compatibility line.

## [1.3.3] - 2025-07-21

### Fixed

- Hardened `StaticFilesMiddleware` against path traversal and invalid file resolution.

## [1.3.2] - 2025-07-11

### Fixed

- Resolved folder path handling in `StaticFilesMiddleware` by normalizing configured directories.

## [1.3.1] - 2025-07-11

### Changed

- Updated documentation configuration and import organization.

## [1.3.0] - 2025-07-11

### Removed

- Python 3.9 support (minimum supported Python is now 3.10).

## [1.2.0] - 2025-07-11

### Changed

- Refreshed development tooling and CI setup.
- Migrated style/code checks to current linting conventions.
- Renamed the middleware base class typo to `BaseMiddleware`
  while keeping a backward-compatible alias.

### Fixed

- Corrected request media parsing variable naming (`content_type_header`).

## [1.1.0] - 2024-11-05

### Added

- Python 3.13 support.
- Additional code-quality checks.

### Fixed

- Type-related fixes across public/internal APIs.

## [1.0.11] - 2024-11-05

### Changed

- Release/build pipeline maintenance updates.

## [1.0.10] - 2024-07-31

### Changed

- Internal updates around test client and compatibility coverage.

## [1.0.9] - 2024-07-31

### Changed

- Version bump and release housekeeping.

## [1.0.8] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.7] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.6] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.5] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.4] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.3] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.2] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.1] - 2024-07-31

### Changed

- Build/release configuration maintenance.

## [1.0.0] - 2024-07-31

### Added

- Python 3.12 support

### Removed

- Python 3.8 support

## [0.74.0] - 2023-06-05

### Added

- request.form now supports max_size

### Changed

- fixed response from test client

## [0.73.0] - 2023-03-06

### Changed

- Drop Python 3.7 support

## [0.72.0] - 2023-03-05

### Added

- BackgroundMiddleware

## [0.70.0] - 2023-03-01

### Changed

- app.on_error only accepts exceptions

## [0.64.0] - 2022-02-09

### Changed

- ResponseFile: change default chunk size to 64Kb

## [0.63.3] - 2021-12-14

### Changed

- Fix closing websockets

## [0.0.1] - 2020-10-29

- First public release

### Added

### Changed

### Removed

[unreleased]: https://github.com/klen/asgi-tools/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/klen/asgi-tools/compare/1.4.0...v2.0.1
[1.4.0]: https://github.com/klen/asgi-tools/compare/1.3.3...1.4.0
[1.3.3]: https://github.com/klen/asgi-tools/compare/1.3.2...1.3.3
[1.3.2]: https://github.com/klen/asgi-tools/compare/1.3.1...1.3.2
[1.3.1]: https://github.com/klen/asgi-tools/compare/1.3.0...1.3.1
[1.3.0]: https://github.com/klen/asgi-tools/compare/1.2.0...1.3.0
[1.2.0]: https://github.com/klen/asgi-tools/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/klen/asgi-tools/compare/1.0.11...1.1.0
[1.0.11]: https://github.com/klen/asgi-tools/compare/1.0.10...1.0.11
[1.0.10]: https://github.com/klen/asgi-tools/compare/1.0.9...1.0.10
[1.0.9]: https://github.com/klen/asgi-tools/compare/1.0.8...1.0.9
[1.0.8]: https://github.com/klen/asgi-tools/compare/1.0.7...1.0.8
[1.0.7]: https://github.com/klen/asgi-tools/compare/1.0.6...1.0.7
[1.0.6]: https://github.com/klen/asgi-tools/compare/1.0.5...1.0.6
[1.0.5]: https://github.com/klen/asgi-tools/compare/1.0.4...1.0.5
[1.0.4]: https://github.com/klen/asgi-tools/compare/1.0.3...1.0.4
[1.0.3]: https://github.com/klen/asgi-tools/compare/1.0.2...1.0.3
[1.0.2]: https://github.com/klen/asgi-tools/compare/1.0.1...1.0.2
[1.0.1]: https://github.com/klen/asgi-tools/compare/1.0.0...1.0.1
[1.0.0]: https://github.com/klen/asgi-tools/compare/0.74.0...1.0.0
[0.74.0]: https://github.com/klen/asgi-tools/compare/0.73.0...0.74.0
[0.73.0]: https://github.com/klen/asgi-tools/compare/0.72.0...0.73.0
[0.72.0]: https://github.com/klen/asgi-tools/compare/0.70.0...0.72.0
[0.70.0]: https://github.com/klen/asgi-tools/compare/0.64.0...0.70.0
[0.64.0]: https://github.com/klen/asgi-tools/compare/0.63.3...0.64.0
[0.63.3]: https://github.com/klen/asgi-tools/compare/0.63.2...0.63.3
[0.63.2]: https://github.com/klen/asgi-tools/compare/0.1.0...0.63.2
[0.1.0]: https://github.com/klen/asgi-tools/compare/0.0.1...0.1.0
[0.0.1]: https://github.com/klen/asgi-tools/releases/tag/0.0.1
