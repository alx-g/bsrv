import configparser
import sys

from .logger import Logger


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
            Config.config_parser.read(path)
        except configparser.MissingSectionHeaderError as e:
            Logger.critical('Error in config file on line {}. {}: {}'.format(e.lineno, repr(e.line),
                                                                             e.message.splitlines(keepends=False)[0]))
            sys.exit(42)
