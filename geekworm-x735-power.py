#!/usr/bin/env python3
"""
Helper script to control power shield switch on/off.
"""
import argparse
import logging
import os
import subprocess
import sys
import time

import pigpio

logger = logging.getLogger("power-service")

# boot indication pin
_x735_BOOT_INFO_GPIO = 12
# button pin
_x735_SHUTDOWN_BUTTON_GPIO = 20
# shutdown info pin
_x735_SHUTDOWN_SIGNAL_GPIO = 5


def _activate_boot_pin(pi):
    # pull up boot pin for power up indication
    logger.info(f"Activate boot into GPIO ({_x735_BOOT_INFO_GPIO})")
    pi.set_mode(_x735_BOOT_INFO_GPIO, pigpio.INPUT)
    pi.set_pull_up_down(_x735_BOOT_INFO_GPIO, pigpio.PUD_UP)

    if pi.read(_x735_BOOT_INFO_GPIO) == 0:
        logger.warning(f"Fail to set boot info GPIO {_x735_BOOT_INFO_GPIO} to 1")


_x735_SHUTDOWN_PULSE = 4
_x735_SHUTDOWN_DELAY = 1.5


def _safe_shutdown():
    logger.info("Send shutdown signal to x735 ...")

    pi = pigpio.pi()

    # ensure that boot pin is active
    _activate_boot_pin(pi)

    # user input with pull up to emulate open drain
    pi.set_mode(_x735_SHUTDOWN_BUTTON_GPIO, pigpio.INPUT)
    pi.set_pull_up_down(_x735_SHUTDOWN_BUTTON_GPIO, pigpio.PUD_UP)
    time.sleep(_x735_SHUTDOWN_PULSE)
    pi.set_pull_up_down(_x735_SHUTDOWN_BUTTON_GPIO, pigpio.PUD_DOWN)
    # small delay to activate hardware
    time.sleep(_x735_SHUTDOWN_DELAY)

    logger.info("Complete")


_x735_REBOOT_PULSE = 0.2
_x735_POWEROFF_PULSE = 0.6


def _monitor_momentary_button():
    pi = pigpio.pi()

    # ensure that boot pin is active
    _activate_boot_pin(pi)

    pi.set_mode(_x735_SHUTDOWN_SIGNAL_GPIO, pigpio.INPUT)

    logger.info(f"Start power control GPIO ({_x735_SHUTDOWN_SIGNAL_GPIO}) monitoring")
    try:
        while True:
            pi.wait_for_edge(_x735_SHUTDOWN_SIGNAL_GPIO, edge=pigpio.EITHER_EDGE)
            shutdown_signal = pi.read(_x735_SHUTDOWN_SIGNAL_GPIO)
            if not shutdown_signal:
                continue

            pulse_start = time.time()
            logger.info(f"Detect pulse start")
            while shutdown_signal:
                time.sleep(0.02)

                pulse_time = time.time() - pulse_start
                if pulse_time > _x735_POWEROFF_PULSE:
                    # reboot pulse
                    logger.info(f"X735 Shutting down (pulse time >= {int(pulse_time * 1000)} ms) ...")
                    subprocess.check_call(['shutdown', '--poweroff', 'now'])
                    sys.exit(0)

                shutdown_signal = pi.read(_x735_SHUTDOWN_SIGNAL_GPIO)

            pulse_time = time.time() - pulse_start
            if pulse_time > _x735_REBOOT_PULSE:
                logger.info(f"X735 Rebooting (pulse time {int(pulse_time * 1000)} ms)...")
                subprocess.check_call(['shutdown', '--reboot', 'now'])
                sys.exit(0)
            else:
                logger.info(f"Invalid control pulse ({int(pulse_time * 1000)} ms)")

    except KeyboardInterrupt:
        logger.info("Shutdown ...")


def main(args=None):
    parser = argparse.ArgumentParser(description='geekwork x735 hat fan daemon')
    parser.add_argument('command', help="power command", choices=['monitor', 'safe-shutdown'])
    parsed_args = parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s  [%(name)s:%(lineno)s]  %(levelname)s - %(message)s')

    if os.geteuid() != 0:
        raise ValueError("script should be run with root permissions")

    if parsed_args.command == 'monitor':
        _monitor_momentary_button()
    elif parsed_args.command == 'safe-shutdown':
        _safe_shutdown()
    else:
        raise ValueError("Unknown command")


if __name__ == '__main__':
    main()
