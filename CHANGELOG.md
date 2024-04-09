# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[unreleased]: https://github.com/klen/asgi-tools/compare/0.74.0...HEAD
[0.74.0]: https://github.com/klen/asgi-tools/compare/0.73.0...0.74.0
[0.73.0]: https://github.com/klen/asgi-tools/compare/0.72.0...0.73.0
[0.72.0]: https://github.com/klen/asgi-tools/compare/0.70.0...0.72.0
[0.70.0]: https://github.com/klen/asgi-tools/compare/0.64.0...0.70.0
[0.64.0]: https://github.com/klen/asgi-tools/compare/0.63.3...0.64.0
[0.63.3]: https://github.com/klen/asgi-tools/compare/0.63.2...0.63.3
[0.63.2]: https://github.com/klen/asgi-tools/compare/0.1.0...0.63.2
[0.1.0]: https://github.com/klen/asgi-tools/compare/0.0.1...0.1.0
[0.0.1]: https://github.com/klen/asgi-tools/releases/tag/0.0.1
