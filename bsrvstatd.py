import argparse
import datetime
import os
import signal
import sys
import threading
from typing import List, NoReturn, Union

from texttable import Texttable

from bsrv import Logger, Config, Cache, Job, Schedule, ScheduleParseError, Hook
from bsrv.tools import gen_json


class BorgStatService:
    def __init__(self, jobs: List[Job], schedule: Schedule):
        self.running = True
        self.jobs = jobs
        self.schedule = schedule

        self.timer_event = threading.Event()
        self.timer: Union['threading.Timer', None] = None

        self.name = 'BorgStatService'

        hook_timeout = Config.getint('stat', 'hook_timeout', fallback=60)
        self.hook_satisfied = Hook('hook_satisfied', Config.get('stat', 'hook_satisfied', fallback=''),
                                   timeout=hook_timeout)
        self.hook_satisfied.set_parent(self)
        self.hook_failed = Hook('hook_failed', Config.get('stat', 'hook_failed', fallback=''), timeout=hook_timeout)
        self.hook_failed.set_parent(self)

        signal.signal(signal.SIGTERM, self.__sigterm_handler)

    def __timer_wakeup(self) -> NoReturn:
        self.timer_event.set()

    def __sigterm_handler(self, signal_number, frame) -> NoReturn:
        Logger.info('Received SIGTERM')
        self.running = False
        self.__timer_wakeup()

    def run(self):
        try:
            last_stat = Cache.get('stat_dt')
            Logger.debug('Loaded last stat datetime: {}'.format(last_stat))
            while self.running:
                if last_stat:
                    next_stat = self.schedule.next(last_stat)
                else:
                    next_stat = self.schedule.next(datetime.datetime.now())

                sleep_time = max(0.0, (next_stat - datetime.datetime.now()).total_seconds())
                Logger.debug(
                    'Determined next stat at {}, waiting for {} s.'.format(next_stat, sleep_time))

                self.timer = threading.Timer(sleep_time, self.__timer_wakeup)
                self.timer.start()
                self.timer_event.wait()

                Logger.info('Timer wakeup.'.format(next_stat))
                self.timer_event.clear()
                if not self.running:
                    Logger.info('Exiting')
                    return

                now = datetime.datetime.now()

                infos = dict()

                tbl = Texttable()
                tbl.set_cols_align(['l', 'c', 'l', 'l', 'l'])
                tbl.set_max_width(80)
                tbl.header(['Job', 'Status', 'Last', 'Age', 'Max Age'])

                satisfied = True

                for job in self.jobs:
                    last = job.get_last_archive_datetime(use_cache=False)
                    age = now - last
                    infos[job.name] = {}
                    if last:
                        if age > job.stat_maxage:
                            satisfied = False
                            infos[job.name]['status'] = 'failed'
                        else:
                            infos[job.name]['status'] = 'satisfied'
                    else:
                        satisfied = False
                        infos[job.name]['status'] = 'unknown'

                    tbl.add_row([job.name, infos[job.name]['status'], last, age, job.stat_maxage])
                    infos[job.name]['last'] = last
                    infos[job.name]['age'] = age.total_seconds()
                    infos[job.name]['maxage'] = job.stat_maxage.total_seconds()

                tbl_str = tbl.draw()
                tbl_str = tbl_str.replace(' ', '\u00a0')

                env = os.environ.copy()
                env['BSRV_INFO_TXT'] = tbl_str.replace('\n', '\\n')
                env['BSRV_INFO_JSON'] = gen_json(infos)
                if satisfied:
                    self.hook_satisfied.trigger(env=env)
                else:
                    self.hook_failed.trigger(env=env)

                last_stat = datetime.datetime.now()
                Cache.set('stat_dt', last_stat)
        finally:
            try:
                self.timer.cancel()
            except:
                pass


def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description='Borg Service daemon.')
    parser.add_argument('-c', metavar='CONFIGFILE', action='store', default='/etc/bsrvd.conf', type=str,
                        help='Path to configuration file.')

    args = parser.parse_args()

    Logger.initialize()

    Config.initialize(args.c)

    Logger.configure()

    Config.check_dirs()

    Cache.initialize('bsrvstatd.cache')

    stat_jobs = []

    # Extract Jobs from Config
    for s in Config.sections():
        if s[0] == ':':
            newjob = Job.from_config(s)
            if newjob:
                if newjob.stat_maxage:
                    stat_jobs.append(newjob)
                    Logger.debug('Registered job {}.'.format(newjob.name))

    if not stat_jobs:
        Logger.warning('No jobs registered!')

    schedule_str = Config.get('stat', 'schedule', fallback=None)
    if not schedule_str:
        Logger.error('No schedule defined in configfile [stat] section')
        sys.exit(1)

    try:
        schedule = Schedule(schedule_str)
    except ScheduleParseError:
        Logger.error('Error in stat schedule definition.')
        sys.exit(2)

    service = BorgStatService(stat_jobs, schedule)
    try:
        service.run()
    except KeyboardInterrupt:
        Logger.info('User requested exit.')


if __name__ == '__main__':
    main()
