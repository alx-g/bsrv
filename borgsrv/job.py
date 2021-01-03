import configparser
import datetime
import enum
import os
import re
import shlex
import subprocess
import threading
import time
from calendar import monthrange
from collections import OrderedDict
from typing import *

from .config import Config
from .logger import Logger
from .tools import parse_json


class Job:
    @staticmethod
    def from_config(cfg_section: str):
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
                schedule=Schedule(Config.get(cfg_section, 'schedule')),
                retry_delay=Config.getint(cfg_section, 'retry_delay')
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
            borg_archive_name_template="%Y-%m-%d_%H-%M-%S",
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
        self.retry_count: int = 0

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
                    Logger.info('[JOB] '+line)
        else:
            Logger.error('[JOB] borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error('[JOB] '+line)
            Logger.warn('[JOB] skipping borg prune due to previous error')
            return False

        params = ['borg', 'prune'] + self.borg_prune_args

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
                    Logger.info('[JOB] '+line)
            return True
        else:
            Logger.error('[JOB] borg returned with non-zero exitcode')
            if stdout_ or stderr_:
                for line in (stdout_ + stderr_).splitlines(keepends=False):
                    Logger.error('[JOB] '+line)
            return False

    def get_last_successful_archive_datetime(self):
        list_of_archives = self.list_archives()
        if list_of_archives:
            list_of_times = sorted([a['time'] for a in list_of_archives], reverse=True)
            if list_of_times:
                return list_of_times[0]
            else:
                return datetime.datetime.fromtimestamp(0)

        Logger.warning('Could not determine last successful archive datetime for job "{}".'.format(self.name))
        return None

    def get_next_archive_datetime(self, last: Union[None, datetime.datetime] = None):
        if last is None:
            last = self.get_last_successful_archive_datetime()
        if last is not None:
            return self.schedule.next(last)
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


class ScheduleParseError(Exception):
    pass


T = TypeVar('T')


class SchedulerQueue(Generic[T]):
    def __init__(self):
        self.waiting: OrderedDict[datetime.datetime, List[T]] = OrderedDict()
        self.lock: threading.Lock = threading.Lock()
        self.hook_update = lambda: []

    def set_update_hook(self, func):
        self.hook_update = func

    def put(self, dt: datetime.datetime, elem: T, hook_enabled: bool = True) -> NoReturn:
        with self.lock:
            if dt in self.waiting.keys():
                self.waiting[dt].append(elem)
            else:
                self.waiting[dt] = [elem]
            self.waiting = OrderedDict((key, self.waiting[key]) for key in sorted(self.waiting.keys()))
        if hook_enabled:
            self.hook_update()

    def get_waiting(self) -> OrderedDict:
        return self.waiting

    def get_next_action(self) -> Tuple[Union[None, datetime.datetime], List[T]]:
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


class Scheduler:
    def __init__(self):
        self.jobs: List[Job] = []
        self.queue: SchedulerQueue[Job] = SchedulerQueue()
        self.queue.set_update_hook(self.__update_wakeup)
        self.timer: Union[None,threading.Timer] = None
        self.timer_event: threading.Event = threading.Event()
        self.timer_reason: WakeupReason = WakeupReason.TIMER
        self.main_thread: threading.Thread = threading.Thread(target=self.scheduler_thread)
        self.jobs_running: Dict[int, threading.Thread] = {}
        self.jobs_running_lock: threading.Lock = threading.Lock()
        self.running: bool = False

    def register(self, job: Job) -> NoReturn:
        self.jobs.append(job)
        next_dt = job.get_next_archive_datetime()
        if next_dt is None:
            Logger.error('[Scheduler] Could not schedule job "{}", no last backup date.'.format(job.name))
        else:
            self.queue.put(next_dt, job, hook_enabled=False)
            Logger.debug('[Scheduler] Registered job "{}"'.format(job.name))

    def start(self) -> NoReturn:
        self.running = True
        self.main_thread.start()

    def stop(self) -> NoReturn:
        self.running = False
        self.timer_reason = WakeupReason.SHUTDOWN
        self.timer_event.set()
        self.main_thread.join()

    def __timer_wakeup(self) -> NoReturn:
        self.timer_reason = WakeupReason.TIMER
        self.timer_event.set()

    def __update_wakeup(self) -> NoReturn:
        self.timer_reason = WakeupReason.UPDATE
        self.timer_event.set()

    def scheduler_thread(self) -> NoReturn:
        Logger.debug('[Scheduler] Launched thread')
        while self.running:
            if len(self.jobs) == 0:
                Logger.warning('No jobs registered, nothing to do')
                break

            next_dt, jobs = self.queue.get_next_action()

            if next_dt is not None:
                sleep_time = max(0.0, (next_dt - datetime.datetime.now()).total_seconds())
                self.timer = threading.Timer(sleep_time, self.__timer_wakeup)

                Logger.debug(
                    '[Scheduler] Determined next action at {}, waiting for {} s.'.format(next_dt, sleep_time))
                self.timer_reason = WakeupReason.TIMER
                self.timer.start()
            else:
                Logger.debug('[Scheduler] All jobs currently running, waiting for one to finish')

            # Wait to be woken up
            self.timer_event.wait()

            if self.timer_reason == WakeupReason.SHUTDOWN:
                try:
                    self.timer.cancel()
                except:
                    pass
                break
            elif self.timer_reason == WakeupReason.UPDATE:
                Logger.debug('[Scheduler] Wakeup due to update, re-evaluating todos.')
                self.timer_event.clear()
                try:
                    self.timer.cancel()
                except:
                    pass
                continue
            elif self.timer_reason == WakeupReason.TIMER:
                Logger.debug('[Scheduler] Wakeup due to timer, launching jobs...')
                try:
                    self.timer.cancel()
                except:
                    pass

            for job in jobs:
                thread = threading.Thread(target=self.job_thread, args=(job,))
                thread.start()
                with self.jobs_running_lock:
                    self.jobs_running[thread.ident] = thread

            self.timer_event.clear()
        Logger.debug('[Scheduler] Exit thread')

    def job_thread(self, job: Job) -> NoReturn:
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

            with self.jobs_running_lock:
                del self.jobs_running[threading.get_ident()]
            self.queue.put(job.get_next_archive_datetime(), job)
        else:
            if job.retry_count > 0:
                Logger.warning('[JOB] Retry {} for job "{}" failed'.format(job.retry_count, job.name))
            job.retry_count += 1
            with self.jobs_running_lock:
                del self.jobs_running[threading.get_ident()]

            if job.retry_delay >= 0:
                scheduled_retry_dt = datetime.datetime.now() + datetime.timedelta(seconds=job.retry_delay)
                Logger.debug('[JOB] Retry for job "{}" scheduled in {}'.format(job.name, datetime.timedelta(seconds=job.retry_delay)))
                self.queue.put(scheduled_retry_dt, job)
            else:
                scheduled_next_dt = job.get_next_archive_datetime(datetime.datetime.now())
                self.queue.put(scheduled_next_dt, job)


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

        self.interval: Union[None, datetime.timedelta] = None
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
            info = match.groupdict()
            self.interval = datetime.timedelta(
                weeks=int(info['weeks'] if info['weeks'] is not None else 0),
                days=int(info['days'] if info['days'] is not None else 0),
                hours=int(info['hours'] if info['hours'] is not None else 0),
                minutes=int(info['minutes'] if info['minutes'] is not None else 0),
            )
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

    def next(self, last: datetime.datetime) -> datetime.datetime:
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
