import configparser
import datetime
import enum
import os
import pathlib
import re
import shlex
import subprocess
import threading
import time
from calendar import monthrange
from collections import OrderedDict
from typing import *

from .cache import Cache
from .config import Config
from .hook import Hook
from .logger import Logger
from .tools import parse_json


def every_expr2dt(match: re.Match) -> datetime.timedelta:
    info = match.groupdict()
    return datetime.timedelta(
        weeks=int(info['weeks'] if info['weeks'] is not None else 0),
        days=int(info['days'] if info['days'] is not None else 0),
        hours=int(info['hours'] if info['hours'] is not None else 0),
        minutes=int(info['minutes'] if info['minutes'] is not None else 0),
    )


class Job:
    @staticmethod
    def from_bsrvstatd_config(cfg_section: str):
        try:
            hook_timeout = Config.getint('borg', 'hook_timeout', fallback=20)

            hook_list_failed = Hook(
                'hook_list_failed',
                Config.get(cfg_section, 'hook_list_failed',
                           fallback=Config.get('borg', 'hook_list_failed', fallback='')),
                timeout=hook_timeout
            )
            hook_list_successful = Hook(
                'hook_list_successful',
                Config.get(cfg_section, 'hook_list_successful',
                           fallback=Config.get('borg', 'hook_list_successful', fallback='')),
                timeout=hook_timeout
            )
            hook_mount_failed = Hook('hook_mount_failed', '', timeout=hook_timeout)
            hook_mount_successful = Hook('hook_mount_successful', '', timeout=hook_timeout)
            hook_umount_failed = Hook('hook_umount_failed', '', timeout=hook_timeout)
            hook_umount_successful = Hook('hook_umount_successful', '', timeout=hook_timeout)
            hook_run_failed = Hook('hook_run_failed', '', timeout=hook_timeout)
            hook_run_successful = Hook('hook_run_successful', '', timeout=hook_timeout)
            hook_give_up = Hook('hook_give_up', '', timeout=hook_timeout)

            every_expr = re.compile(r'^\s*((?P<weeks>\d+)\s*w(eeks?)?)?'
                                    r'\s*((?P<days>\d+)\s*d(ays?)?)?'
                                    r'\s*((?P<hours>\d+)\s*h(ours?)?)?'
                                    r'\s*((?P<minutes>\d+)\s*m(in(utes?)?)?)?\s*$', re.IGNORECASE)

            match = every_expr.fullmatch(Config.get(cfg_section, 'stat_maxage', fallback=''))
            if match:
                stat_maxage = every_expr2dt(match)
            else:
                stat_maxage = None

            return Job(
                name=cfg_section,
                borg_repo=Config.get(cfg_section, 'borg_repo'),
                borg_rsh=Config.get(cfg_section, 'borg_rsh', fallback='ssh'),
                borg_archive_name_template=None,
                borg_passphrase=Config.get(cfg_section, 'borg_passphrase'),
                borg_prune_args=None,
                borg_create_args=None,
                schedule=None,
                retry_delay=None,
                retry_max=None,
                stat_maxage=stat_maxage,
                hook_list_failed=hook_list_failed,
                hook_list_successful=hook_list_successful,
                hook_mount_failed=hook_mount_failed,
                hook_mount_successful=hook_mount_successful,
                hook_umount_failed=hook_umount_failed,
                hook_umount_successful=hook_umount_successful,
                hook_run_failed=hook_run_failed,
                hook_run_successful=hook_run_successful,
                hook_give_up=hook_give_up
            )
        except configparser.NoOptionError as e:
            Logger.error('Error in config file: Missing or invalid key for job "{}": {}'.format(cfg_section, e.message))
            return None

    @staticmethod
    def from_bsrvd_config(cfg_section: str):
        try:
            hook_timeout = Config.getint('borg', 'hook_timeout', fallback=20)

            hook_list_failed = Hook(
                'hook_list_failed',
                Config.get(cfg_section, 'hook_list_failed',
                           fallback=Config.get('borg', 'hook_list_failed', fallback='')),
                timeout=hook_timeout
            )
            hook_list_successful = Hook(
                'hook_list_successful',
                Config.get(cfg_section, 'hook_list_successful',
                           fallback=Config.get('borg', 'hook_list_successful', fallback='')),
                timeout=hook_timeout
            )
            hook_mount_failed = Hook(
                'hook_mount_failed',
                Config.get(cfg_section, 'hook_mount_failed',
                           fallback=Config.get('borg', 'hook_mount_failed', fallback='')),
                timeout=hook_timeout
            )
            hook_mount_successful = Hook(
                'hook_mount_successful',
                Config.get(cfg_section, 'hook_mount_successful',
                           fallback=Config.get('borg', 'hook_mount_successful', fallback='')),
                timeout=hook_timeout
            )
            hook_umount_failed = Hook(
                'hook_umount_failed',
                Config.get(cfg_section, 'hook_umount_failed',
                           fallback=Config.get('borg', 'hook_umount_failed', fallback='')),
                timeout=hook_timeout
            )
            hook_umount_successful = Hook(
                'hook_umount_successful',
                Config.get(cfg_section, 'hook_umount_successful',
                           fallback=Config.get('borg', 'hook_umount_successful', fallback='')),
                timeout=hook_timeout
            )
            hook_run_failed = Hook(
                'hook_run_failed',
                Config.get(cfg_section, 'hook_run_failed',
                           fallback=Config.get('borg', 'hook_run_failed', fallback='')),
                timeout=hook_timeout
            )
            hook_run_successful = Hook(
                'hook_run_successful',
                Config.get(cfg_section, 'hook_run_successful',
                           fallback=Config.get('borg', 'hook_run_successful', fallback='')),
                timeout=hook_timeout
            )
            hook_give_up = Hook(
                'hook_give_up',
                Config.get(cfg_section, 'hook_give_up',
                           fallback=Config.get('borg', 'hook_give_up', fallback='')),
                timeout=hook_timeout
            )

            every_expr = re.compile(r'^\s*((?P<weeks>\d+)\s*w(eeks?)?)?'
                                    r'\s*((?P<days>\d+)\s*d(ays?)?)?'
                                    r'\s*((?P<hours>\d+)\s*h(ours?)?)?'
                                    r'\s*((?P<minutes>\d+)\s*m(in(utes?)?)?)?\s*$', re.IGNORECASE)

            return Job(
                name=cfg_section,
                borg_repo=Config.get(cfg_section, 'borg_repo'),
                borg_rsh=Config.get(cfg_section, 'borg_rsh', fallback='ssh'),
                borg_archive_name_template=Config.get(cfg_section, 'borg_archive_name_template',
                                                      fallback='%Y-%m-%d_%H-%M-%S'),
                borg_passphrase=Config.get(cfg_section, 'borg_passphrase'),
                borg_prune_args=shlex.split(Config.get(cfg_section, 'borg_prune_args')),
                borg_create_args=shlex.split(Config.get(cfg_section, 'borg_create_args')),
                schedule=Schedule(Config.get(cfg_section, 'schedule')),
                retry_delay=Config.getint(cfg_section, 'retry_delay', fallback=60),
                retry_max=Config.getint(cfg_section, 'retry_max', fallback=3),
                stat_maxage=None,
                hook_list_failed=hook_list_failed,
                hook_list_successful=hook_list_successful,
                hook_mount_failed=hook_mount_failed,
                hook_mount_successful=hook_mount_successful,
                hook_umount_failed=hook_umount_failed,
                hook_umount_successful=hook_umount_successful,
                hook_run_failed=hook_run_failed,
                hook_run_successful=hook_run_successful,
                hook_give_up=hook_give_up
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
            retry_delay,
            retry_max,
            hook_list_failed: Hook,
            hook_list_successful: Hook,
            hook_mount_failed: Hook,
            hook_mount_successful: Hook,
            hook_umount_failed: Hook,
            hook_umount_successful: Hook,
            hook_run_failed: Hook,
            hook_run_successful: Hook,
            hook_give_up: Hook,
            stat_maxage: Union[datetime.timedelta, None] = None,
            borg_archive_name_template: Union[str, None] = "%Y-%m-%d_%H-%M-%S",
            borg_rsh='ssh'
    ):
        self.name: str = name
        self.borg_repo: str = borg_repo
        self.borg_passphrase: str = borg_passphrase
        self.borg_rsh: str = borg_rsh
        self.borg_archive_name_template: str = borg_archive_name_template
        self.borg_prune_args: str = borg_prune_args
        self.borg_create_args: str = borg_create_args
        self.schedule: Schedule = schedule
        self.retry_delay: int = retry_delay
        self.retry_max: int = retry_max
        self.retry_count: int = 0
        self.last_archive_date = Cache.get('job_{}_last_dt'.format(self.name))
        self.mount_dir = os.path.join(Config.get('borg', 'mount_dir', fallback='/tmp/bsrvd-mount'), self.name)
        self.stat_maxage = stat_maxage

        if self.borg_archive_name_template is None or self.borg_create_args is None or self.borg_prune_args is None or self.schedule is None or self.retry_delay is None or self.retry_max is None:
            self.runnable = False
        else:
            self.runnable = True

        self.hook_list_failed: 'Hook' = hook_list_failed
        self.hook_list_failed.set_parent(self)
        self.hook_list_successful: 'Hook' = hook_list_successful
        self.hook_list_successful.set_parent(self)
        self.hook_mount_failed: 'Hook' = hook_mount_failed
        self.hook_mount_failed.set_parent(self)
        self.hook_mount_successful: 'Hook' = hook_mount_successful
        self.hook_mount_successful.set_parent(self)
        self.hook_umount_failed: 'Hook' = hook_umount_failed
        self.hook_umount_failed.set_parent(self)
        self.hook_umount_successful: 'Hook' = hook_umount_successful
        self.hook_umount_successful.set_parent(self)
        self.hook_run_failed: 'Hook' = hook_run_failed
        self.hook_run_failed.set_parent(self)
        self.hook_run_successful: 'Hook' = hook_run_successful
        self.hook_run_successful.set_parent(self)
        self.hook_give_up: 'Hook' = hook_give_up
        self.hook_give_up.set_parent(self)

    def __eq__(self, other):
        return other.name == self.name

    def run(self):
        if not self.runnable:
            raise RuntimeError('Job "{}" is not configured properly to be run.'.format(self.name))

        env = os.environ.copy()
        env['BORG_REPO'] = self.borg_repo
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir', fallback='/var/cache/bsrvd')

        now = time.time()

        archive_name = ('::{:%s}' % (self.borg_archive_name_template,)).format(datetime.datetime.fromtimestamp(now))
        params = [Config.get('borg', 'binary', fallback='borg'), 'create'] + [archive_name] + self.borg_create_args

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
                    Logger.info('[JOB] ' + line)
        else:
            Logger.error('[JOB] borg returned with non-zero exitcode')
            hook_lines = ''
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error('[JOB] ' + line)
                    hook_lines += line + '\\n'
            Logger.warn('[JOB] skipping borg prune due to previous error')
            self.hook_run_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
            return False

        params = [Config.get('borg', 'binary', fallback='borg'), 'prune'] + self.borg_prune_args

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
                    Logger.info('[JOB] ' + line)
            self.hook_run_successful.trigger(env={'BSRV_JOB': self.name})
            return True
        else:
            Logger.error('[JOB] borg returned with non-zero exitcode')
            hook_lines = ''
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error('[JOB] ' + line)
                    hook_lines += line + '\\n'
            self.hook_run_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
            return False

    def get_last_archive_datetime(self, use_cache: bool = True):
        if not use_cache or not self.last_archive_date:
            list_of_archives = self.list_archives()
            if list_of_archives:
                list_of_times = sorted([a['time'] for a in list_of_archives], reverse=True)
                if list_of_times:
                    return list_of_times[0]
                else:
                    return datetime.datetime.fromtimestamp(0)

            Logger.warning('Could not determine last successful archive datetime for job "{}".'.format(self.name))
            return None
        else:
            return self.last_archive_date

    def set_last_archive_datetime(self, dt: 'datetime.datetime'):
        self.last_archive_date = dt
        Cache.set('job_{}_last_dt'.format(self.name), dt)

    def get_next_archive_datetime(self, last: Union[None, 'datetime.datetime'] = None):
        if last is None:
            last = self.get_last_archive_datetime()
        if last is not None:
            return self.schedule.next(last)
        else:
            return None

    def list_archives(self):
        env = os.environ.copy()
        env['BORG_REPO'] = self.borg_repo
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir', fallback='/var/cache/bsrvd')

        params = ['borg', 'list', '--json']

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
            try:
                borg_archives = parse_json(stdout_)['archives']
                self.hook_list_successful.trigger(env={'BSRV_JOB': self.name})
                return borg_archives
            except Exception:
                hook_lines = ''
                for line in stdout_.splitlines(keepends=False):
                    hook_lines += line + '\\n'
                self.hook_list_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
                Logger.error('borg returned non-parsable json')
        else:
            Logger.error('borg returned with non-zero exitcode')
            hook_lines = ''
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
                    hook_lines += line + '\\n'
            self.hook_list_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
            return None

    def get_info(self):
        archives = self.list_archives()

        env = os.environ.copy()
        env['BORG_REPO'] = self.borg_repo
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir', fallback='/var/cache/bsrvd')

        params = ['borg', 'info', '--json']

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
            try:
                borg_info = parse_json(stdout_)
            except Exception:
                Logger.error('borg returned non-parsable json')
                borg_info = {}
        else:
            Logger.error('borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
            borg_info = {}

        borg_info['archives'] = archives
        return borg_info

    def mount(self):
        env = os.environ.copy()
        env['BORG_RSH'] = self.borg_rsh
        env['BORG_PASSPHRASE'] = self.borg_passphrase
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir', fallback='/var/cache/bsrvd')

        pathlib.Path(self.mount_dir).mkdir(exist_ok=True)
        if Config.get_global('root'):
            params = ['borg', 'mount', '-o', 'allow_other', self.borg_repo, self.mount_dir]
        else:
            params = ['borg', 'mount', self.borg_repo, self.mount_dir]

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
            self.hook_mount_successful.trigger(env={'BSRV_JOB': self.name})
            return True
        else:
            Logger.error('borg returned with non-zero exitcode')
            hook_lines = ''
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
                    hook_lines += line + '\\n'
            self.hook_mount_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
            return False

    def umount(self):
        env = os.environ.copy()
        env['BORG_BASE_DIR'] = Config.get('borg', 'base_dir', fallback='/var/cache/bsrvd')

        params = ['borg', 'umount', self.mount_dir]

        tokens = [shlex.quote(token) for token in params]
        Logger.info('[JOB] Running \'%s\'', ' '.join(tokens))

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
            self.hook_umount_successful.trigger(env={'BSRV_JOB': self.name})
            return True
        else:
            Logger.error('borg returned with non-zero exitcode')
            hook_lines = ''
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error(line)
                    hook_lines += line + '\\n'
            self.hook_umount_failed.trigger(env={'BSRV_JOB': self.name, 'BSRV_ERROR': hook_lines})
            return False

    def status(self):
        last = self.get_last_archive_datetime()
        return {
            'job_last_successful': last.isoformat() if last else 'none',
            'job_next_suggested': self.get_next_archive_datetime(last).isoformat() if last else 'none',
            'job_retry': str(self.retry_count)
        }


class ScheduleParseError(Exception):
    pass


class SchedulerQueue:
    def __init__(self):
        self.waiting: 'OrderedDict' = OrderedDict()
        self.lock: 'threading.Lock' = threading.Lock()
        self.hook_update = lambda: []

    def set_update_hook(self, func):
        self.hook_update = func

    def __reorder(self):
        self.waiting = OrderedDict((key, self.waiting[key]) for key in sorted(self.waiting.keys()))

    def when(self, elem: Any) -> Union[None, 'datetime.datetime']:
        for this_dt, this_elems in self.waiting.items():
            for k in range(len(this_elems)):
                this_elem = this_elems[k]
                if elem is not None and this_elem == elem:
                    return this_dt

        return None

    def put(self, elem: Any, dt: 'datetime.datetime', hook_enabled: bool = True) -> NoReturn:
        with self.lock:
            if dt in self.waiting.keys():
                self.waiting[dt].append(elem)
            else:
                self.waiting[dt] = [elem]
            self.__reorder()
        if hook_enabled:
            self.hook_update()

    def delete(self, elem: Any, hook_enabled: bool = True) -> bool:
        with self.lock:
            found = False
            for this_dt, this_elems in self.waiting.items():
                for k in range(len(this_elems)):
                    this_elem = this_elems[k]
                    if elem is not None and this_elem == elem:
                        if len(this_elems) == 1:
                            del self.waiting[this_dt]
                        else:
                            del self.waiting[this_dt][k]
                        found = True
                        break
                if found:
                    break
            self.__reorder()

        if found and hook_enabled:
            self.hook_update()

        return found

    def move(self, elem: Any, dt: 'datetime.datetime', hook_enabled: bool = True) -> bool:
        if self.delete(elem, hook_enabled=False):
            self.put(elem, dt, hook_enabled=hook_enabled)
            return True
        else:
            return False

    def get_waiting(self) -> 'OrderedDict':
        return self.waiting

    def get_next_action(self) -> Tuple[Union[None, 'datetime.datetime'], List[Any]]:
        with self.lock:
            try:
                dt, items = self.waiting.popitem(last=False)
            except (IndexError, KeyError):
                items = []

            if items:
                return dt, items
            else:
                return None, []


class WakeupReason(enum.Enum):
    SHUTDOWN = enum.auto()
    TIMER = enum.auto()
    UPDATE = enum.auto()
    PAUSE = enum.auto()


class Scheduler:
    def __init__(self):
        self.jobs: List['Job'] = []
        self.queue: 'SchedulerQueue' = SchedulerQueue()
        self.queue.set_update_hook(self.__update_wakeup)
        self.timer: Union[None, 'threading.Timer'] = None
        self.timer_event: 'threading.Event' = threading.Event()
        self.timer_reason: 'WakeupReason' = WakeupReason.TIMER
        self.main_thread: 'threading.Thread' = threading.Thread(target=self.scheduler_thread)
        self.threads_running: Dict[int, 'threading.Thread'] = {}
        self.jobs_running: List['Job'] = []
        self.jobs_running_lock: 'threading.Lock' = threading.Lock()
        self.running: bool = False
        self.next_dt: Union['datetime.datetime', None] = None
        self.next_jobs: List['Job'] = []
        self.status_update_callback = lambda job_name, sched_status, retry: []
        self.pause_callback = lambda is_paused: []
        self.paused = False

    def find_job_by_name(self, job_name: str) -> Union[None, 'Job']:
        list_of_jobs = [job.name for job in self.jobs]
        if not job_name in list_of_jobs:
            return None
        else:
            try:
                return self.jobs[list_of_jobs.index(job_name)]
            except (IndexError, KeyError):
                return None

    def get_job_status(self, job: 'Job') -> Dict[str, str]:
        job_status = job.status()

        if job in self.jobs_running:
            job_status['schedule_status'] = 'running'
            job_status['schedule_dt'] = 'now'
        elif job in self.next_jobs:
            job_status['schedule_status'] = 'next'
            job_status['schedule_dt'] = self.next_dt.isoformat()
        else:
            queue_dt = self.queue.when(job)
            if queue_dt:
                job_status['schedule_status'] = 'wait'
                job_status['schedule_dt'] = queue_dt.isoformat()
            else:
                job_status['schedule_status'] = 'none'
                job_status['schedule_dt'] = 'none'

        return job_status

    def schedule(self, job: 'Job', dt: 'datetime.datetime', hook_enabled: bool = True) -> bool:
        if job not in self.jobs:
            return False
        else:
            self.queue.put(job, dt, hook_enabled=hook_enabled)
            return True

    def unschedule(self, job: 'Job') -> bool:
        if job not in self.jobs:
            return False
        else:
            return self.queue.delete(job)

    def register(self, job: 'Job') -> NoReturn:
        self.jobs.append(job)
        next_dt = job.get_next_archive_datetime()
        if next_dt is None:
            Logger.error('[Scheduler] Could not register job "{}", no last backup date.'.format(job.name))
        else:
            if self.schedule(job, next_dt, hook_enabled=False):
                Logger.info('[Scheduler] Registered job "{}"'.format(job.name))
            else:
                Logger.error('[Scheduler] Could not register job "{}", unknown error'.format(job.name))

    def advance_to_now(self, job: 'Job') -> bool:
        if job in self.next_jobs:
            self.next_jobs.remove(job)
            self.queue.put(job, datetime.datetime.now())
            return True
        else:
            return self.queue.move(job, datetime.datetime.now())

    def start(self) -> NoReturn:
        self.running = True
        self.main_thread.start()

    def stop(self) -> NoReturn:
        self.running = False
        self.timer_reason = WakeupReason.SHUTDOWN
        self.timer_event.set()
        self.main_thread.join()

    def pause(self) -> NoReturn:
        if not self.paused:
            self.paused = True
            self.__pause_wakeup()

    def unpause(self) -> NoReturn:
        if self.paused:
            self.__pause_wakeup()
            self.paused = False

    def __timer_wakeup(self) -> NoReturn:
        self.timer_reason = WakeupReason.TIMER
        self.timer_event.set()

    def __update_wakeup(self) -> NoReturn:
        self.timer_reason = WakeupReason.UPDATE
        self.timer_event.set()

    def __pause_wakeup(self) -> NoReturn:
        self.timer_reason = WakeupReason.PAUSE
        self.timer_event.set()

    def scheduler_thread(self) -> NoReturn:
        Logger.debug('[Scheduler] Launched thread')
        while self.running:
            if len(self.jobs) == 0:
                Logger.warning('No jobs registered, nothing to do')
                break

            self.next_dt, self.next_jobs = self.queue.get_next_action()
            for job in self.next_jobs:
                self.status_update_callback(job.name, 'next', job.retry_count)

            if self.next_dt is not None:
                sleep_time = max(0.0, (self.next_dt - datetime.datetime.now()).total_seconds())
                self.timer = threading.Timer(sleep_time, self.__timer_wakeup)

                Logger.debug(
                    '[Scheduler] Determined next action at {}, waiting for {} s.'.format(self.next_dt, sleep_time))
                self.timer_event.clear()
                self.timer.start()
            else:
                Logger.debug('[Scheduler] All jobs currently running, waiting for one to finish')

            # Wait to be woken up
            self.timer_event.wait()

            if self.timer_reason == WakeupReason.SHUTDOWN:
                if self.timer:
                    self.timer.cancel()
                break
            elif self.timer_reason == WakeupReason.UPDATE:
                Logger.debug('[Scheduler] Wakeup due to update, re-evaluating todos.')
                self.timer_event.clear()
                if self.timer:
                    self.timer.cancel()
                while self.next_jobs:
                    job = self.next_jobs.pop()
                    self.queue.put(job, self.next_dt)
                    self.status_update_callback(job.name, 'wait', job.retry_count)
                continue
            elif self.timer_reason == WakeupReason.PAUSE:
                Logger.debug('[Scheduler] Wakeup due to pause trigger. Clearing timer and going to pause...')
                self.timer_event.clear()
                if self.timer:
                    self.timer.cancel()

                self.pause_callback(True)

                self.timer_event.wait()
                Logger.debug('[Scheduler] Wakeup from pause, re-evaluating todos.')
                self.timer_event.clear()

                self.pause_callback(False)

                while self.next_jobs:
                    job = self.next_jobs.pop()
                    self.queue.put(job, self.next_dt)
                    self.status_update_callback(job.name, 'wait', job.retry_count)
                continue
            elif self.timer_reason == WakeupReason.TIMER:
                Logger.debug('[Scheduler] Wakeup due to timer, launching jobs...')
                if self.timer:
                    self.timer.cancel()

            while self.next_jobs:
                job = self.next_jobs.pop()
                thread = threading.Thread(target=self.job_thread, args=(job,))
                thread.start()
                with self.jobs_running_lock:
                    self.threads_running[thread.ident] = thread
                    self.jobs_running.append(job)
                self.status_update_callback(job.name, 'running', job.retry_count)

            self.timer_event.clear()
        Logger.debug('[Scheduler] Exit thread')

    def job_thread(self, job: 'Job') -> NoReturn:
        if job.retry_count > 0:
            Logger.info('[JOB] Launching retry {} for job "{}"...'.format(job.retry_count, job.name))
        else:
            Logger.info('[JOB] Launching job "{}"...'.format(job.name))

        successful = job.run()
        if successful:
            if job.retry_count > 0:
                Logger.info(
                    '[JOB] Retry {} for job "{}" completed successfully'.format(job.retry_count, job.name))
                job.retry_count = 0
            else:
                Logger.info('[JOB] job "{}" completed successfully'.format(job.name))
                job.retry_count = 0

            job.set_last_archive_datetime(datetime.datetime.now())
            self.queue.put(job, job.get_next_archive_datetime())
            with self.jobs_running_lock:
                del self.threads_running[threading.get_ident()]
                self.jobs_running.remove(job)
            self.status_update_callback(job.name, 'wait', job.retry_count)
        else:
            give_up = job.retry_count >= job.retry_max
            if job.retry_count > 0:
                if give_up:
                    Logger.error('[JOB] Retry {} for job "{}" failed. Giving up.'.format(job.retry_count, job.name))
                    job.retry_count = -1
                else:
                    Logger.warning('[JOB] Retry {} for job "{}" failed'.format(job.retry_count, job.name))
                    if job.retry_count < 0:
                        job.retry_count = 0
                    job.retry_count += 1
            else:
                if give_up:
                    Logger.error('[JOB] Job "{}" failed. Giving up.'.format(job.name))
                    job.retry_count = -1
                else:
                    Logger.warning('[JOB] Job "{}" failed.'.format(job.name))
                    if job.retry_count < 0:
                        job.retry_count = 0
                    job.retry_count += 1

            if not give_up:
                scheduled_retry_dt = datetime.datetime.now() + datetime.timedelta(seconds=job.retry_delay)
                Logger.debug('[JOB] Retry for job "{}" scheduled in {}'.format(job.name, datetime.timedelta(
                    seconds=job.retry_delay)))
                self.queue.put(job, scheduled_retry_dt)
            else:
                job.hook_give_up.trigger(env={'BSRV_JOB': self.name})
                scheduled_next_dt = job.get_next_archive_datetime(datetime.datetime.now())
                self.queue.put(job, scheduled_next_dt)

            with self.jobs_running_lock:
                del self.threads_running[threading.get_ident()]
                self.jobs_running.remove(job)

            self.status_update_callback(job.name, 'wait', job.retry_count)


class Schedule:
    def __init__(self, txt: str):
        every_expr = re.compile(r'^\s*@every\s*((?P<weeks>\d+)\s*w(eeks?)?)?'
                                r'\s*((?P<days>\d+)\s*d(ays?)?)?'
                                r'\s*((?P<hours>\d+)\s*h(ours?)?)?'
                                r'\s*((?P<minutes>\d+)\s*m(in(utes?)?)?)?\s*$', re.IGNORECASE)
        weekly_expr = re.compile(r'^\s*@weekly\s*$', re.IGNORECASE)
        daily_expr = re.compile(r'^\s*@daily\s*$', re.IGNORECASE)
        hourly_expr = re.compile(r'^\s*@hourly\s*$', re.IGNORECASE)
        cron_expr = re.compile(r'^\s*(?P<min>\d+(-\d+)?(,\d+(-\d+)?)*|\*(/\d+)?)'
                               r'\s+(?P<hour>\d+(-\d+)?(,\d+(-\d+)?)*|\*(/\d+)?)'
                               r'\s+(?P<mday>\d+(-\d+)?(,\d+(-\d+)?)*|\*(/\d+)?)'
                               r'\s+(?P<month>\d+(-\d+)?(,\d+(-\d+)?)*|\*(/\d+)?)'
                               r'\s+(?P<wday>\d+(-\d+)?(,\d+(-\d+)?)*|\*(/\d+)?)\s*$', re.IGNORECASE)

        self.cron_type_expr = re.compile(r'^(?P<fixed>\d+(-\d+)?(,\d+(-\d+)?)*)|(?P<div>\*/\d+)|(?P<all>\*)$')

        self.interval: Union[None, 'datetime.timedelta'] = None
        self.crontab: Union[None, Dict[str, Iterable[int]]] = None

        match = weekly_expr.fullmatch(txt)
        if match:
            self.interval = datetime.timedelta(weeks=1)
            return

        match = daily_expr.fullmatch(txt)
        if match:
            self.interval = datetime.timedelta(days=1)
            return

        match = hourly_expr.fullmatch(txt)
        if match:
            self.interval = datetime.timedelta(hours=1)
            return

        match = every_expr.fullmatch(txt)
        if match:
            self.interval = every_expr2dt(match)
            return

        match = cron_expr.fullmatch(txt)
        if match:
            info = match.groupdict()

            self.crontab = {
                'min': self.__parse_cron_elem(info['min'], range(0, 59 + 1)),
                'hour': self.__parse_cron_elem(info['hour'], range(0, 23 + 1)),
                'mday': self.__parse_cron_elem(info['mday'], range(1, 31 + 1), onebased=True),
                'month': self.__parse_cron_elem(info['month'], range(1, 12 + 1), onebased=True),
                'wday': self.__parse_cron_elem(info['wday'], range(0, 7))
            }
            return

        raise ScheduleParseError('Invalid schedule specification.')

    def __parse_cron_elem(self, elem: str, possible_vals: Iterable[int], onebased: bool = False) -> Iterable[int]:
        match = self.cron_type_expr.fullmatch(elem)
        if not match:
            raise ScheduleParseError('Invalid schedule specification.')

        sub_info = match.groupdict()
        vals = []

        if sub_info['fixed'] is not None:
            blocks = [block.split('-') for block in sub_info['fixed'].split(',')]
            for b in blocks:
                if len(b) == 1:
                    vals.append(int(b[0]))
                elif len(b) == 2:
                    vals += range(int(b[0]), int(b[1]) + 1)
                else:
                    raise ScheduleParseError('Invalid schedule specification.')

        elif sub_info['div'] is not None:
            factor = int(sub_info['div'][2:])
            if onebased:
                vals = [p for p in possible_vals if (p - 1) % factor == 0]
            else:
                vals = [p for p in possible_vals if p % factor == 0]

        elif sub_info['all'] is not None:
            vals = possible_vals

        else:
            raise ScheduleParseError('Invalid schedule specification.')

        return vals

    def next(self, last: 'datetime.datetime') -> 'datetime.datetime':
        if self.interval is not None:
            return last + self.interval
        elif self.crontab is not None:
            for year in [last.year, last.year + 1]:
                start_month = 1 if year > last.year else last.month

                for month in sorted(set(range(start_month, 12 + 1)).intersection(self.crontab['month'])):
                    start_day = 1 if month > last.month or year > last.year else last.day
                    end_day = monthrange(year, month)[1]

                    allday_list = sorted(range(start_day, end_day + 1))

                    weekday_list = []
                    for day in allday_list:
                        if (datetime.date(year=year, month=month, day=day).weekday() + 1) % 7 in self.crontab['wday']:
                            weekday_list.append(day)

                    monthday_list = sorted(set(allday_list).intersection(self.crontab['mday']))

                    relevant_day_list = set([])
                    if len(weekday_list) < len(allday_list):
                        relevant_day_list = relevant_day_list.union(weekday_list)
                    if len(monthday_list) < len(allday_list):
                        relevant_day_list = relevant_day_list.union(monthday_list)
                    if len(relevant_day_list) == 0:
                        relevant_day_list = allday_list

                    for day in sorted(relevant_day_list):
                        start_hour = 0 if day > last.day or month > last.month or year > last.year else last.hour

                        for hour in sorted(set(range(start_hour, 23 + 1)).intersection(self.crontab['hour'])):
                            start_minute = 0 if hour > last.hour or day > last.day or month > last.month or year > last.year else last.minute + 1

                            for minute in sorted(set(range(start_minute, 59 + 1)).intersection(self.crontab['min'])):
                                return datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)

        else:
            raise RuntimeError('Invalid internal schedule configuration.')
