# vznncv-geekwork-x735-v2.5

Debian package version of [geekwork-x735-v2.5](https://github.com/geekworm-com/x735-v2.5) scripts.

![geekwork-x735-v2.5](docs/geekworm-x735-v2.5.jpg)

Unlike original scripts it has the following differences:

- safe shutdown script is integrated as special *systemd* service and is activated automatically by default `shutdown`
  command.
- FAN uses hardware PWM implementation.
- FAN start/stop parameters can be adjusted via '/etc/geekworm/config.conf' configuration.

## Installation

1. Download package from [github releases](https://github.com/vznncv/vznncv-geekworm-x735-v2.5/releases) section
   or build package locally with `package/build_debian_package.sh` script.

2. Copy and install package to raspberry pi:

   ```shell
   sudo dpkg -i geekworm-x735-v2.5_<package_version>_all.deb
   sudo apt-get install --fix-broken
   ```

## Uninstallation

```
sudo apt-get remove geekworm-x735-v2.5
```

### Power consumption optimization

Fan script uses [pigpiod](https://abyz.me.uk/rpi/pigpio/pigpiod.html), that consumes 4-6% of CPU in idle state.
To reduce CPU usage you can disable alert functionality of *pigpiod*, as it isn't requires by fan scripts:

1. Edit file `/usr/lib/systemd/system/pigpiod.service` to add `-m -s 10` to daemon startup options:

   ```
   # ...
   [Service]
   ExecStart=/usr/bin/pigpiod -l -m -s 10
   # ...
   ```

2. Reload systemd and restart service:

   ```
   sudo systemctl daemon-reload
   sudo systemctl restart pigpiod
   ```

### Configuration

If you need to check fan settings (minimal temperature to start fan, etc.), you need to edit
`/etc/geekworm/config.conf` configuration file and restart fan service:

```shell
sudo systemctl restart geekworm-x735-fan
```
