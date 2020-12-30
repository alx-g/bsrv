import enum
import logging
import logging.handlers
import sys

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
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        Logger.addHandler(console_handler)
        Logger.setLevel(logging.DEBUG)
        Logger.info('Startup.')

    @staticmethod
    def configure():
        from .config import Config

        logging_target_str = Config.get('logging', 'target', fallback='stdout')
        if logging_target_str not in log_target_dict.keys():
            Logger.error('Error in config file: logging target needs to be "file", "journald" or "stdout". '
                         'Falling back to "stdout"')
            logging_target = LogTarget.STDOUT
        else:
            logging_target = log_target_dict[logging_target_str]

        log_path = Config.get('logging', 'path', fallback='.')

        sysd = None

        if logging_target == LogTarget.JOURNAL:
            sysd = init_systemd_logging(logger=Logger.logger)
        elif logging_target == LogTarget.FILE:
            file_handler = logging.handlers.TimedRotatingFileHandler(log_path, when='midnight',
                                                                     backupCount=Config.getint('logging', 'max_logfiles',
                                                                                               fallback=7))
            file_handler.setFormatter(log_formatter)
            Logger.addHandler(file_handler)

        # set logging level
        Logger.setLevel(log_level_dict[Config.get('logging', 'log_level', fallback='INFO').lower()])

        if sysd is not None and not sysd:
            Logger.warning('Could not connect to journald logging. This daemon needs to be run by systemd. '
                           'Now only logging to stdout')

        Logger.info('Configured logging.')
