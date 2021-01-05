import configparser
import sys
import os
import pathlib

from typing import List

from .logger import Logger, LogTarget


class ConfigMeta(type):
    def __getattr__(cls, item):
        if cls.config_parser is None:
            raise RuntimeError('Config singleton was never initialized with file path.')
        else:
            return getattr(cls.config_parser, item)


class Config(metaclass=ConfigMeta):
    config_parser = None

    @staticmethod
    def initialize(path):
        try:
            Config.config_parser = configparser.ConfigParser()
            Config.config_parser._interpolation = configparser.ExtendedInterpolation()
            read_ok = Config.config_parser.read(path)
            if not read_ok:
                Logger.critical('Config file "{}" not found'.format(path))
                sys.exit(42)
        except configparser.MissingSectionHeaderError as e:
            Logger.critical('Error in config file on line {}. {}: {}'.format(e.lineno, repr(e.line),
                                                                             e.message.splitlines(keepends=False)[0]))
            sys.exit(42)

    @staticmethod
    def check_dirs():
        paths: List[pathlib.Path] = []

        if LogTarget.FILE in Logger.logging_targets:
            log_path = Config.get('logging', 'path')
            log_dir, log_file = os.path.split(log_path)
            paths.append(pathlib.Path(log_dir))

        paths.append(pathlib.Path(Config.get('borg', 'base_dir')))
        paths.append(pathlib.Path(Config.get('borg', 'mount_dir')))

        failed = False

        for path in paths:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not os.access(path, os.R_OK | os.X_OK | os.W_OK):
                failed = True
                Logger.critical('Cannot write to "{}"'.format(path))
        if failed:
            sys.exit(33)

