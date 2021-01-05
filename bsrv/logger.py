import enum
import logging
import logging.handlers
import sys
from typing import List

from systemdlogging.toolbox import init_systemd_logging


class LogTarget(enum.Enum):
    FILE = enum.auto()
    JOURNAL = enum.auto()
    STDOUT = enum.auto()


log_level_dict = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

log_target_dict = {
    'file': LogTarget.FILE,
    'files': LogTarget.FILE,
    'journal': LogTarget.JOURNAL,
    'journald': LogTarget.JOURNAL,
    'systemd': LogTarget.JOURNAL,
    'stdout': LogTarget.STDOUT
}

log_formatter = logging.Formatter("%(asctime)s [%(levelname)8.8s] %(message)s", datefmt="%Y-%m-%d %H-%M-%S")


class LoggerMeta(type):
    def __getattr__(cls, item):
        if cls.logger is None:
            raise RuntimeError('Logger was never initialized.')
        else:
            return getattr(cls.logger, item)


class Logger(metaclass=LoggerMeta):
    logger = None

    @staticmethod
    def initialize():
        Logger.logger = logging.getLogger()
        Logger.logger.propagate = False

    @staticmethod
    def configure():
        from .config import Config

        logging_targets_rawstr = Config.get('logging', 'target', fallback='stdout')
        logging_targets_str = [s.strip() for s in logging_targets_rawstr.split(',')]
        logging_targets: List[LogTarget] = []

        for t in logging_targets_str:
            if t not in log_target_dict.keys():
                print('Error in config file: logging target can only be "file", "journald" or "stdout". '
                      'Ignoring "{}"'.format(t), file=sys.stderr)
            else:
                logging_targets.append(log_target_dict[t])

        log_path = Config.get('logging', 'path', fallback='/var/log/bsrvd.log')

        if LogTarget.STDOUT in logging_targets:
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(log_formatter)
            Logger.addHandler(stdout_handler)

        if LogTarget.JOURNAL in logging_targets:
            if not init_systemd_logging(logger=Logger.logger):
                print('Could not connect to journald logging. This daemon needs to be run by systemd. '
                      'Now only logging to stdout', file=sys.stderr)

        if LogTarget.FILE in logging_targets:
            try:
                file_handler = logging.handlers.TimedRotatingFileHandler(log_path,
                                                                         when='midnight',
                                                                         backupCount=Config.getint('logging',
                                                                                                   'max_logfiles',
                                                                                                   fallback=7))
            except (PermissionError, FileNotFoundError):
                print('Can not write to logfile {}. Now only logging to stdout'.format(log_path), file=sys.stderr)
            else:
                file_handler.setFormatter(log_formatter)
                Logger.addHandler(file_handler)

        # set logging level
        Logger.setLevel(log_level_dict[Config.get('logging', 'log_level', fallback='INFO').lower()])

        Logger.info('Started Logger.')
