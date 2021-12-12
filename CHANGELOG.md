# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- Refactor `geekworm-x735-power.py` script to use *sysfs* instead of *pigpio*. It helps to avoid problems with
  network availability during shutdown.
### Fixed
- Fixed systemd safe shutdown/reboot hooks.

## [0.1.0] - 2021-09-12
### Added
- Added shield fan control service
- Added shield power signal monitor service
- Added safe shutdown service
