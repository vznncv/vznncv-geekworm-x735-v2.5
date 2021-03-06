# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2021-12-16
### Added
- Added `/etc/geekworm-x735/config.conf` file with fan configuration options.
### Changed
- Refactor `geekworm-x735-power` script to use *sysfs* instead of *pigpio*. It helps to avoid problems with
  network availability during shutdown.
- Switch GPIO input pull up/down mode to output pull/push for power control pins to simplify `geekworm-x735-power`
  script implementation.
- Refactor debian package build scripts to use `dpgk-buildpackage` instead of `dpkg-deb`
### Fixed
- Fixed systemd safe shutdown/reboot hooks.


## [0.1.0] - 2021-09-12
### Added
- Added shield fan control service
- Added shield power signal monitor service
- Added safe shutdown service
