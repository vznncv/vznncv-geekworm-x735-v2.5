#!/usr/bin/env python3
"""
Helper script to control power shield switch on/off.
"""
import argparse
import logging
import os
import subprocess
import time

logger = logging.getLogger("power-service")


#
# Minimal native GPIO control implementation.
#

class _SYSFSGPIOManager:
    _SYSFS_GPIO_PATH = '/sys/class/gpio'

    def __init__(self):
        pass

    @classmethod
    def _check_pin(cls, pin):
        if not 0 <= pin < 54:
            raise ValueError(f"Unknown pin number {pin}")

    def _export_and_get_pin_path(self, pin):
        self._check_pin(pin)
        gpio_path = os.path.join(self._SYSFS_GPIO_PATH, f'gpio{pin}')
        if os.path.exists(gpio_path):
            return gpio_path
        # try to export pin
        with open(os.path.join(self._SYSFS_GPIO_PATH, 'export'), 'w') as f:
            f.write(str(pin))
        if not os.path.exists(gpio_path):
            raise ValueError(f"Fail to activate pin {pin}")
        return gpio_path

    def _gpio_direction_path(self, pin):
        return os.path.join(self._export_and_get_pin_path(pin), 'direction')

    def _gpio_value_path(self, pin):
        return os.path.join(self._export_and_get_pin_path(pin), 'value')

    def get_mode(self, pin):
        gpio_direction_path = self._gpio_direction_path(pin)
        with open(gpio_direction_path) as f:
            value = f.read().strip()
        if value == "in":
            return "input"
        elif value == "out":
            return "output"
        else:
            raise ValueError(f"Unknown pin mode: {value}")

    def set_mode(self, pin, mode):
        gpio_direction_path = self._gpio_direction_path(pin)
        if mode == "input":
            value = "in"
        elif mode == "output":
            value = "out"
        else:
            raise ValueError(f"Unknown mode: {mode}")
        prev_value = self.get_mode(pin)
        if prev_value != value:
            with open(gpio_direction_path, 'w') as f:
                return f.write(value)

    def set_value(self, pin, value):
        gpio_value_path = self._gpio_value_path(pin)
        with open(gpio_value_path, 'w') as f:
            f.write(str(value))

    def get_value(self, pin):
        gpio_value_path = self._gpio_value_path(pin)
        with open(gpio_value_path, 'r') as f:
            raw_value = f.read()
        return int(raw_value.strip())


#
# X735 power manager
#

class _PowerManagerX735:
    # boot indication pin
    BOOT_INFO_GPIO = 12
    # shutdown control pin
    SHUTDOWN_CONTROL_GPIO = 20
    # shutdown signal pin
    SHUTDOWN_SIGNAL_GPIO = 5

    def __init__(self):
        self.gpio = _SYSFSGPIOManager()

    def _activate_pin(self, pin, name, mode, value=0):
        prev_mode = self.gpio.get_mode(pin)
        prev_value = self.gpio.get_value(pin)
        if mode != prev_mode or (mode != 'input' and value != prev_value):
            logger.info(f"Activate/reset {name} pin ({pin}, mode: {mode})")
            self.gpio.set_mode(pin, mode)
            if mode != 'input':
                self.gpio.set_value(pin, value)

    def init_pins(self):
        """
        Reset power control pins to default values.
        """
        # reset shutdown control pin
        self._activate_pin(self.SHUTDOWN_CONTROL_GPIO, 'showdown control', 'output', 0)
        # reset shutdown info pin
        self._activate_pin(self.SHUTDOWN_SIGNAL_GPIO, 'shutdown signal', 'input')
        # activate indication pin
        self._activate_pin(self.BOOT_INFO_GPIO, 'boot info', 'output', 1)

    def _send_shutdown_signal(self, signal_name, pulse_length, post_pulse_delay=1):
        # ensure that pins are initialized
        self.init_pins()

        # send signal
        logger.info(f"Send {signal_name} signal to x735 ...")
        self.gpio.set_value(self.SHUTDOWN_CONTROL_GPIO, 1)
        time.sleep(pulse_length)
        self.gpio.set_value(self.SHUTDOWN_CONTROL_GPIO, 0)
        time.sleep(post_pulse_delay)

        logger.info("Complete")

    def safe_poweroff(self):
        """
        Safe shutdown.
        """
        self._send_shutdown_signal(signal_name="shutdown", pulse_length=4)

    def safe_reboot(self):
        """
        Safe reboot.
        """
        self._send_shutdown_signal(signal_name="reboot", pulse_length=1)

    SHUTDOWN_SIGNAL_LOW_PULL_PERIOD = 0.2
    SHUTDOWN_SIGNAL_HIGH_PULL_PERIOD = 0.02

    SHUTDOWN_SIGNAL_REBOOT_PULSE = 0.2
    SHUTDOWN_SIGNAL_POWEROFF_PULSE = 0.6

    SHUTDOWN_TIMEOUT = 30

    def monitor(self):
        """
        Monitor shutdown/reboot signal.
        """
        try:

            while True:
                self._monitor_loop()
                time.sleep(self.SHUTDOWN_TIMEOUT)
                logger.warning(
                    f"System haven't been shut down after {self.SHUTDOWN_TIMEOUT} seconds. Continue monitoring!"
                )
        except KeyboardInterrupt:
            logger.info("Shutdown ...")

    def _shutdown_system(self, shutdown_command):
        result = subprocess.run(['systemctl', 'is-system-running'], encoding='utf-8', stdout=subprocess.PIPE)
        state = result.stdout.strip()
        # don't call any shutdown command if system is stopping
        if state == 'stopping':
            return
        if shutdown_command == 'poweroff':
            subprocess.check_output(['shutdown', '--poweroff', 'now'])
        elif shutdown_command == 'reboot':
            subprocess.check_output(['shutdown', '--reboot', 'now'])
        else:
            raise ValueError(f"Unknown shutdown command: {shutdown_command}")

    def _monitor_loop(self):
        """
        Monitor shutdown/reboot signal.
        """
        # ensure that pins are initialized
        self.init_pins()

        logger.info(f"Start power control pin ({self.SHUTDOWN_SIGNAL_GPIO}) monitoring")

        while True:
            time.sleep(self.SHUTDOWN_SIGNAL_LOW_PULL_PERIOD)
            shutdown_signal = self.gpio.get_value(self.SHUTDOWN_SIGNAL_GPIO)
            if not shutdown_signal:
                continue

            logger.info("Detect pulse start")
            pulse_start = time.time()
            time.sleep(self.SHUTDOWN_SIGNAL_HIGH_PULL_PERIOD)

            while True:
                pulse_time = time.time() - pulse_start
                pulse_time_ms = int(pulse_time * 1000)
                shutdown_signal = self.gpio.get_value(self.SHUTDOWN_SIGNAL_GPIO)
                if not shutdown_signal:
                    break

                if pulse_time > self.SHUTDOWN_SIGNAL_POWEROFF_PULSE:
                    # reboot pulse
                    logger.info(f"Shutting down (pulse time >= {pulse_time_ms} ms) ...")
                    self._shutdown_system('poweroff')
                    return
                time.sleep(self.SHUTDOWN_SIGNAL_HIGH_PULL_PERIOD)

            if pulse_time > self.SHUTDOWN_SIGNAL_REBOOT_PULSE:
                logger.info(f"X735 Rebooting (pulse time {int(pulse_time * 1000)} ms)...")
                self._shutdown_system('reboot')
                return
            else:
                logger.info(f"Invalid control pulse ({int(pulse_time * 1000)} ms)")


#
# CLI interface
#

def main(args=None):
    parser = argparse.ArgumentParser(description='geekwork x735 hat fan daemon')
    parser.add_argument('command', help="power command", choices=[
        'monitor',
        'safe-shutdown', 'safe-poweroff',
        'safe-reboot'
    ])
    parsed_args = parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s  [%(name)s:%(lineno)s]  %(levelname)s - %(message)s')

    if os.geteuid() != 0:
        raise ValueError("script should be run with root permissions")

    power_manager = _PowerManagerX735()

    if parsed_args.command == 'monitor':
        power_manager.monitor()
    elif parsed_args.command == 'safe-shutdown' or parsed_args.command == 'safe-poweroff':
        power_manager.safe_poweroff()
    elif parsed_args.command == 'safe-reboot':
        power_manager.safe_reboot()
    else:
        raise ValueError(f"Unknown command: {parsed_args.command}")


if __name__ == '__main__':
    main()
