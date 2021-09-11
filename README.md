# vznncv-geekwork-x735-v2.5

Debian package version of [geekwork-x735-v2.5](https://github.com/geekworm-com/x735-v2.5) scripts.

## Installation

1. Build package on a control machine:

  ```shell
  ./build_debian_package.sh
  ```

2. Copy and install package to raspberry pi:

   ```shell
   sudo dpkg -i vznncv-geekwork-x735-v2.5_0.1.0-1_all.deb
   sudo apt-get install --fix-broken
   ```

3. Reboot raspberry pi (it may be required if for pigpiod installation).

## Service logs

1. Fan service status:

  ```
  systemctl status geekworm-x735-fan.service
  ```

2. Fan logs:

  ```
  journalctl -u geekworm-x735-fan.service
  ```
