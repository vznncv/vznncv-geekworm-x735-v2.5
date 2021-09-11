#!/usr/bin/env python3
import argparse
import logging
import time

import pigpio

_FAN_PWM_UPDATE_PERIOD = 2
_LOG_UPDATER_PERIOD = 5 * 60
logger = logging.getLogger("fan-service")

_FAN_PWM_PIN = 13
_TEMP_SYS_PATH = '/sys/class/thermal/thermal_zone0/temp'


def _get_cpu_temp():
    with open(_TEMP_SYS_PATH, 'rb') as f:
        raw_temp = f.read().strip()
    return int(raw_temp) / 1000.0


_CPU_FAN_TEMP_MIN = 40
_CPU_FAN_TEMP_MIN_DUTY_CYCLE = 0.2
_CPU_FAN_TEMP_MAX = 65
_CPU_FAN_PWM_FREQ = 25000


class _FANController:
    _CPU_FAN_TEMP_MIN_START = 50
    _CPU_FAN_TEMP_MIN_STOP = 45

    _CPU_FAN_DS_MIN = 0.2
    _CPU_FAN_PWM_FREQ = 25000

    _CPU_FAN_TEMP_MIN = 45
    _CPU_FAN_TEMP_MAX = 65

    def __init__(self):
        self._activate = False

    def get_duty_cycle(self, temp):
        duty_cycle = (temp - self._CPU_FAN_TEMP_MIN) / (self._CPU_FAN_TEMP_MAX - self._CPU_FAN_TEMP_MIN)
        if duty_cycle > 1.0:
            duty_cycle = 1.0
        elif duty_cycle < self._CPU_FAN_DS_MIN:
            duty_cycle = self._CPU_FAN_DS_MIN

        if temp > self._CPU_FAN_TEMP_MIN_START:
            self._activate = True
        elif temp > self._CPU_FAN_TEMP_MIN_STOP:
            if not self._activate:
                duty_cycle = 0.0
        else:
            self._activate = False
            duty_cycle = 0.0

        return duty_cycle


def _cpu_temp_to_duty_cycle(temp):
    if temp <= _CPU_FAN_TEMP_MIN:
        return 0.0
    else:
        duty_cycle = (temp - _CPU_FAN_TEMP_MIN) / (_CPU_FAN_TEMP_MAX - _CPU_FAN_TEMP_MIN)
        duty_cycle = duty_cycle * (1 - _CPU_FAN_TEMP_MIN_DUTY_CYCLE) + _CPU_FAN_TEMP_MIN_DUTY_CYCLE

    if duty_cycle < 0:
        duty_cycle = 0.0
    elif duty_cycle > 1:
        duty_cycle = 1.0
    return duty_cycle


def _to_pigpio_hw_dutycycle(value):
    value = int(value * 1_000_000)
    if value < 0:
        value = 0
    elif value > 1_000_000:
        value = 1_000_000
    return value


def main(args=None):
    parser = argparse.ArgumentParser(description='geekwork x735 hat fan daemon')
    parsed_args = parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s  [%(name)s:%(lineno)s]  %(levelname)s - %(message)s')

    pi = pigpio.pi()
    # configure fan pin
    pi.set_mode(_FAN_PWM_PIN, pigpio.OUTPUT)

    logger.info(f"Start ...")
    next_log = time.time()

    fan_controller = _FANController()

    try:
        while True:
            cpu_temp = _get_cpu_temp()
            duty_cycle = fan_controller.get_duty_cycle(cpu_temp)
            pi.hardware_PWM(_FAN_PWM_PIN, _CPU_FAN_PWM_FREQ, _to_pigpio_hw_dutycycle(duty_cycle))
            if time.time() >= next_log:
                logger.info(f"CPU: {cpu_temp:.1f} C; Fan: {duty_cycle:.1%}")
                next_log += _LOG_UPDATER_PERIOD

            time.sleep(_FAN_PWM_UPDATE_PERIOD)
    except KeyboardInterrupt:
        logger.info("Shutdown ...")
    finally:
        cpu_temp = _get_cpu_temp()
        logger.info(f"Stop. CPU: {cpu_temp:.1f} C; Fan: ${0:.1%} (disable)")
        # disable pwm
        pi.hardware_PWM(_FAN_PWM_PIN, _CPU_FAN_PWM_FREQ, 0)
        # disable pin
        pi.set_mode(_FAN_PWM_PIN, pigpio.INPUT)


if __name__ == '__main__':
    main()
