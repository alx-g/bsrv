import configparser
import os
import pathlib
import sys
from typing import List

from .logger import Logger, LogTarget
from .demote import DemotionSubprocess


class ConfigMeta(type):
    def __getattr__(cls, item):
        if cls.config_parser is None:
            raise RuntimeError('Config singleton was never initialized with file path.')
        else:
            return getattr(cls.config_parser, item)


class Config(metaclass=ConfigMeta):
    config_parser = None
    globals = {}

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
    def check_dirs(check_log_dir=True, check_base_dir=True, check_mount_dir=True):
        paths: List[pathlib.Path] = []

        if LogTarget.FILE in Logger.logging_targets:
            log_path = Config.get('logging', 'path')
            log_directory, log_file = os.path.split(log_path)
            if check_log_dir:
                paths.append(pathlib.Path(log_directory))

        if check_base_dir:
            paths.append(pathlib.Path(Config.get('borg', 'base_dir')))
        if check_mount_dir:
            paths.append(pathlib.Path(Config.get('borg', 'mount_dir')))

        failed = False

        for path in paths:
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
            if not os.access(path, os.R_OK | os.X_OK | os.W_OK):
                failed = True
                Logger.critical('Cannot write to "{}"'.format(path))
        if failed:
            sys.exit(33)

    @staticmethod
    def check_user_dirs(demotion: DemotionSubprocess, mount_name: str) -> bool:
        paths: List[pathlib.Path] = []

        paths.append(pathlib.Path(Config.get('borg', 'base_dir')) / ('u_' + demotion.name))
        paths.append(pathlib.Path(Config.get('borg', 'mount_dir')) / ('u_' + demotion.name) / mount_name)

        for path in paths:
            try:
                path.mkdir(mode=0o755, parents=True, exist_ok=True)
            except:
                Logger.critical('Cannot create user dir "{}"'.format(path))
                return False

            try:
                os.chown(path.as_posix(), demotion.uid, demotion.gid)
            except:
                Logger.critical('Cannot chown user dir "{}"'.format(path))
                return False

            try:
                os.chmod(path.as_posix(), 0o755)
            except:
                Logger.critical('Cannot chmod user dir "{}"'.format(path))
                return False

            if not os.access(path, os.R_OK | os.X_OK | os.W_OK):
                Logger.critical('Cannot write to user dir "{}"'.format(path))
                return False

        return True

    @staticmethod
    def set_global(key, val):
        Config.globals[key] = val

    @staticmethod
    def get_global(key):
        try:
            return Config.globals[key]
        except:
            return None
