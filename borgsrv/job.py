import datetime
import os
import shlex
import subprocess
import time
import configparser
import datetime

from .config import Config
from .logger import Logger
from .tools import parse_json
from .schedule import Schedule, ScheduleParseError


class Job:
    @staticmethod
    def from_config(cfg_section):
        try:
            return Job(
                name=cfg_section,
                borg_repo=Config.get(cfg_section, 'borg_repo'),
                borg_rsh=Config.get(cfg_section, 'borg_rsh', fallback='ssh'),
                borg_archive_name_template=Config.get(cfg_section, 'borg_archive_name_template',
                                                      fallback='%Y-%m-%d_%H-%M-%S'),
                borg_passphrase=Config.get(cfg_section, 'borg_passphrase'),
                borg_prune_args=shlex.split(Config.get(cfg_section, 'borg_prune_args')),
                borg_create_args=shlex.split(Config.get(cfg_section, 'borg_create_args')),
                schedule=Schedule(Config.get(cfg_section, 'schedule'))
            )
        except ScheduleParseError:
            Logger.error('Error in config file: Invalid schedule specification for job "{}"'.format(cfg_section))
            return None

        except configparser.NoOptionError as e:
            Logger.error('Error in config file: Missing or invalid key for job "{}": {}'.format(cfg_section, e.message))
            return None

    def __init__(
            self,
            name,
            borg_repo,
            borg_passphrase,
            borg_create_args,
            borg_prune_args,
            schedule,
            borg_archive_name_template="%Y-%m-%d_%H-%M-%S",
            borg_rsh='ssh'
    ):
        self.name = name
        self.borg_repo = borg_repo
        self.borg_passphrase = borg_passphrase
        self.borg_rsh = borg_rsh
        self.borg_archive_name_template = borg_archive_name_template
        self.borg_prune_args = borg_prune_args
        self.borg_create_args = borg_create_args
        self.schedule = schedule

    def run(self):
        env = os.environ.copy()
        env['BORG_REPO'] = self.borg_repo
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir')

        now = time.time()

        archive_name = ('::{:%s}' % (self.borg_archive_name_template,)).format(datetime.datetime.fromtimestamp(now))
        params = ['borg', 'create'] + [archive_name] + self.borg_create_args

        tokens = [shlex.quote(token) for token in params]
        Logger.info('Running \'%s\'', ' '.join(tokens))

        p = subprocess.Popen(
            params,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = p.communicate()
        stdout_ = stdout.decode()
        stderr_ = stderr.decode()

        if p.returncode == 0:
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.info(line)
        else:
            Logger.error('borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
            Logger.warn('skipping borg prune due to previous error')
            return False

        params = ['borg', 'prune'] + self.borg_prune_args

        tokens = [shlex.quote(token) for token in params]
        Logger.info('Running \'%s\'', ' '.join(tokens))

        p = subprocess.Popen(
            params,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = p.communicate()
        stdout_ = stdout.decode()
        stderr_ = stderr.decode()

        if p.returncode == 0:
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.info(line)
            return True
        else:
            Logger.error('borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
            return False

    def get_last_successful_archive_date(self):
        list_of_times = sorted([a['time'] for a in self.list_archives()], reverse=True)
        if list_of_times:
            return list_of_times[0]
        else:
            return None

    def list_archives(self):
        env = os.environ.copy()
        env['BORG_REPO'] = self.borg_repo
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir')

        params = ['borg', 'list', '--json']

        p = subprocess.Popen(
            params,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = p.communicate()
        stdout_ = stdout.decode()
        stderr_ = stderr.decode()
        if p.returncode == 0:
            return parse_json(stdout_)['archives']
        else:
            Logger.error('borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
            return None
