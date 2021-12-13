#!/usr/bin/env python3
"""
Helper script to control geekwork x735 PWM FAN
"""
import argparse
import configparser
import logging
import os.path
import time
from collections import namedtuple
from typing import Optional

import pigpio

logger = logging.getLogger("fan-service")


def _build_number_parser(min=None, max=None, optional=False):
    def validator(value):
        if value is None or value == '':
            if optional:
                return None
            else:
                raise ValueError(f"value mustn't be empty, but it was: {value}")

        try:
            parsed_value = float(value)
        except ValueError:
            raise ValueError(f"value should number, but it was {value}")

        if min is not None and parsed_value < min:
            raise ValueError(f"value should greater or equal than {min}, but it was {value}")
        if max is not None and parsed_value > max:
            raise ValueError(f"value should less or equal than {max}, but it was {value}")

        return parsed_value

    return validator


_OptionInfo = namedtuple('_OptionInfo', ('name', 'description', 'default_value', 'type'))


class _Config:
    _CONFIG_DESCRIPTION = {
        'pigpio': [
            _OptionInfo('port', 'pigpio Daemon port', None, _build_number_parser(min=0, optional=True)),
        ],
        'fan': [
            _OptionInfo('update_period', 'FAN update period', 2, _build_number_parser(min=0)),
            _OptionInfo('log_period', 'FAN state log peroid', 60, _build_number_parser(min=0)),

            _OptionInfo('duty_cycle_min', 'minimal pwm duty cycle', 0.2, _build_number_parser(min=0, max=1)),
            _OptionInfo('duty_cycle_max', 'maximal pwm duty cycle', 1.0, _build_number_parser(min=0, max=1)),
            _OptionInfo('min_power_start_temp', 'minimal temperature to start FAN', 48, _build_number_parser()),
            _OptionInfo('min_power_stop_temp', 'minimal temperature to stop FAN', 42, _build_number_parser()),
            _OptionInfo('max_power_temp', 'temperature that corresponds max FAN power', 60, _build_number_parser()),
        ]
    }

    @classmethod
    def add_cli_args(cls, parser: argparse.ArgumentParser):
        for section_name, section_options in cls._CONFIG_DESCRIPTION.items():
            for option in section_options:
                name = f'--{section_name}-{option.name}'.lower().replace('_', '-')
                dest = f'{section_name}_{option.name}'
                parser.add_argument(name, default=None, dest=dest, help=option.description)
        return parser

    _DEFAULT_CONFIG_PATH = '/etc/geekworm-x735/config.conf'

    def __init__(self, path, parser_options: Optional[argparse.Namespace] = None):

        # load options from configuration file
        config = configparser.ConfigParser()
        if path:
            config.read(path)
        elif os.path.exists(self._DEFAULT_CONFIG_PATH):
            config.read(self._DEFAULT_CONFIG_PATH)
        else:
            logger.warning(f"No config file is specify and default config file {self._DEFAULT_CONFIG_PATH}"
                           f"isn't found. Default values for all options will be used.")
        raw_config = {}
        for section_name, section_config in config.items():
            if section_name == configparser.DEFAULTSECT:
                continue
            if section_name not in self._CONFIG_DESCRIPTION:
                logger.error(f"Unknown section [{section_name}]")
                continue
            section_options = self._CONFIG_DESCRIPTION[section_name]

            raw_section_config = raw_config[section_name] = {}
            section_config_dict = {k: v for k, v in section_config.items()}
            for option in section_options:
                if option in section_config_dict:
                    raw_section_config[option.name] = section_config_dict.pop(option.name)
            if section_config_dict:
                raise ValueError(f"Unknown options of the section [{section_name}]: {section_config_dict}")
        # add options from parser
        for section_name, section_options in self._CONFIG_DESCRIPTION.items():
            for option in section_options:
                dest = f'{section_name}_{option.name}'
                value = getattr(parser_options, dest, None)
                if value is not None:
                    raw_config.setdefault(section_name, {})[option.name] = value

        # parse/validate options
        self._parsed_config = {}
        for section_name, section_options in self._CONFIG_DESCRIPTION.items():
            parsed_section_config = self._parsed_config[section_name] = {}
            raw_section_config = raw_config.get(section_name, {})
            for option in section_options:
                raw_value = raw_section_config.get(option.name, option.default_value)
                try:
                    parsed_section_config[option.name] = option.type(raw_value)
                except Exception as e:
                    raise ValueError(f"Fail to process option {section_name}/{option.name}") from e
        if not self.min_power_stop_temp <= self.min_power_start_temp <= self.max_power_temp:
            raise ValueError(
                f"Temperature should be min_power_stop_temp <= min_power_start_temp <= max_power_temp, "
                f"but it was: {self.min_power_stop_temp} - {self.min_power_start_temp} - {self.max_power_temp}"
            )
        if not self.duty_cycle_min <= self.duty_cycle_max:
            raise ValueError(
                f"Duty cycle should be duty_cycle_min <= duty_cycle_max, "
                f"but it was: {self.duty_cycle_min} - {self.duty_cycle_max}"
            )

    @property
    def update_period(self) -> float:
        return self._parsed_config['fan']['update_period']

    @property
    def log_period(self) -> float:
        return self._parsed_config['fan']['log_period']

    @property
    def duty_cycle_min(self) -> float:
        return self._parsed_config['fan']['duty_cycle_min']

    @property
    def duty_cycle_max(self) -> float:
        return self._parsed_config['fan']['duty_cycle_max']

    @property
    def min_power_start_temp(self) -> float:
        return self._parsed_config['fan']['min_power_start_temp']

    @property
    def min_power_stop_temp(self) -> float:
        return self._parsed_config['fan']['min_power_stop_temp']

    @property
    def max_power_temp(self) -> float:
        return self._parsed_config['fan']['max_power_temp']

    @property
    def pigpio_port(self) -> Optional[int]:
        return self._parsed_config['pigpio']['port']

    def log_params(self):
        logger.info("Effective service options:")
        for section_name, section_config in self._parsed_config.items():
            for option_name, value in section_config.items():
                logger.info(f"- {section_name}/{option_name}: {value}")


class _TemperatureManager:
    _TEMP_SYS_PATH = '/sys/class/thermal/thermal_zone0/temp'

    def get_cpu_temp(self) -> float:
        with open(self._TEMP_SYS_PATH, 'rb') as f:
            raw_temp = f.read().strip()
        return int(raw_temp) / 1000.0


class _X735FANManager:
    FAN_PWM_GPIO = 13
    FAN_PWM_FREQ = 25000

    def __init__(self, config):
        self._temp_manager = _TemperatureManager()
        self._config = config
        pi_args = {}
        if self._config.pigpio_port:
            pi_args['port'] = self._config.pigpio_port
        self._pi = pigpio.pi(**pi_args)

        # previous duty cycle
        self._prev_duty_cycle = 0.0

    def close(self):
        self._pi.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _update_duty_cycle(self, temp: float) -> float:
        if temp <= self._config.min_power_stop_temp:
            result = 0
        elif temp <= self._config.min_power_start_temp:
            if self._prev_duty_cycle > 0:
                result = self._config.duty_cycle_min
            else:
                result = 0
        elif temp <= self._config.max_power_temp:
            k = (temp - self._config.min_power_start_temp) / \
                (self._config.max_power_temp - self._config.min_power_start_temp)
            result = self._config.duty_cycle_min + (self._config.duty_cycle_max - self._config.duty_cycle_min) * k
        else:
            result = self._config.duty_cycle_max
        self._prev_duty_cycle = result
        return result

    @staticmethod
    def _to_pigpio_hw_dutycycle(value):
        value = int(value * 1_000_000)
        if value < 0:
            value = 0
        elif value > 1_000_000:
            value = 1_000_000
        return value

    def _fan_enable(self):
        self._pi.set_mode(self.FAN_PWM_GPIO, pigpio.OUTPUT)

    def _fan_disable(self):
        self._pi.set_mode(self.FAN_PWM_FREQ, pigpio.INPUT)

    def _fan_set_duty_cycle(self, value):
        self._pi.hardware_PWM(self.FAN_PWM_GPIO, self.FAN_PWM_FREQ, self._to_pigpio_hw_dutycycle(value))

    def main_loop(self):
        logger.info(f"Start x735 temperature/fan monitor")
        next_log = time.time()

        cpu_temp = self._temp_manager.get_cpu_temp()
        duty_cycle = 0

        try:
            # configure fan pin
            self._fan_enable()

            while True:
                cpu_temp = self._temp_manager.get_cpu_temp()
                duty_cycle = self._update_duty_cycle(cpu_temp)
                self._fan_set_duty_cycle(duty_cycle)
                if next_log <= time.time():
                    next_log += self._config.log_period
                    logger.info(f"CPU temperature: {cpu_temp:.2f}. Fan: {duty_cycle:.1%}")

                time.sleep(self._config.update_period)
        except KeyboardInterrupt:
            # force log of last cpu temperature/duty cycle
            logger.info(f"CPU temperature: {cpu_temp:.2f}. Fan: {duty_cycle:.1%}")
            raise
        finally:
            # disable pwm
            self._fan_set_duty_cycle(0)
            # disable pin
            self._fan_disable()


def _main_loop(config):
    while True:
        try:
            with _X735FANManager(config=config) as manager:
                manager.main_loop()
        except Exception:
            logger.exception("Fan service error. Retry in 30 seconds ...")
        time.sleep(30)


def main(args=None):
    parser = argparse.ArgumentParser(description='geekwork x735 fan manager')
    parser.add_argument('-c', '--config', help='Config file')
    _Config.add_cli_args(parser)
    parsed_args = parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s  [%(name)s:%(lineno)s]  %(levelname)s - %(message)s')

    config = _Config(parsed_args.config, parser_options=parsed_args)
    config.log_params()
    try:
        _main_loop(config)
    except KeyboardInterrupt:
        logger.info("Shutdown ...")


if __name__ == '__main__':
    main()
