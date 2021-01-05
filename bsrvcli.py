#!/usr/bin/env python3
import argparse
import json
import sys
import time
import threading

from dasbus.error import DBusError
from dasbus.client.proxy import get_object_path

from bsrv import SERVICE_IDENTIFIER

parser = argparse.ArgumentParser(description='Borg service CLI')

m_group = parser.add_mutually_exclusive_group()
m_group.add_argument('-l', '--list-jobs', action='store_true', default=False, help='List names of loaded jobs.')
m_group.add_argument('-s', '--status', metavar='JOB_NAME', default=None, action='store', type=str,
                     help='Display status of job with given name.')
m_group.add_argument('-r', '--run', metavar='JOB_NAME', default=None, action='store', type=str,
                     help='Manually run a job now. This may have an influence on future scheduled actions for this job.')
m_group.add_argument('--shutdown', action='store_true', default=False, help='Shutdown daemon')

parser.add_argument('--json', action='store_true', default=False,
                    help='Instead of outputting nicely formatted data, instead output data as JSON')

args = parser.parse_args()

proxy = None

try:
    proxy = SERVICE_IDENTIFIER.get_proxy()
    if not proxy:
        sys.exit(1)

    if args.list_jobs:
        jobs = proxy.GetLoadedJobs()
        if args.json:
            print(json.dumps(jobs))
        else:
            print('bsrvd has currently loaded the following jobs:')
            for job in jobs:
                print(job)
    elif args.status is not None:
        status = proxy.GetJobStatus(args.status)
        if not status:
            print('bsrvd has no job loaded with the name "{}"'.format(args.status))
            sys.exit(1)

        if args.json:
            print(json.dumps(status))
        else:
            print('+' + '=' * 78 + '+')
            print('| %-53s | %-20s |' % ('Description', 'Value'))
            print('+' + '=' * 78 + '+')
            print('| %-53s | %-20s |' % ('Time of last successful borg archive', status['job_last_successful']))
            print('+' + '-' * 78 + '+')
            print('| %-53s | %-20s |' % ('Time of next suggested borg archive', status['job_next_suggested']))
            print('+' + '-' * 78 + '+')
            print('| %-53s | %-20s |' % ('Number of retries since last successful run', status['job_retry']))
            print('+' + '-' * 78 + '+')
            print('| %-53s | %-20s |' % ('Scheduling status of this job.', status['schedule_status']))
            print('| %-53s | %-20s |' % ('> next: Currently selected for processing at next', ''))
            print('| %-53s | %-20s |' % ('        action time.', ''))
            print('| %-53s | %-20s |' % ('> wait: Action scheduled at later point in time', ''))
            print('| %-53s | %-20s |' % ('> none: No action scheduled for this job. This ', ''))
            print('| %-53s | %-20s |' % ('        means no action will ever be run and likely', ''))
            print('| %-53s | %-20s |' % ('        results from invalid configuration.', ''))
            print('+' + '-' * 78 + '+')
            print('| %-53s | %-20s |' % ('Next action time for this job', status['schedule_dt']))
            print('+' + '=' * 78 + '+')
    elif args.run:
        if not proxy.RunJob(args.run):
            sys.exit(1)
    elif args.shutdown:
        proxy.Shutdown()

        try:
            for k in range(300):
                proxy.GetLoadedJobs()
                time.sleep(0.01)
            sys.exit(1)
        except DBusError:
            sys.exit(0)

except DBusError:
    print('Could not connect to daemon, is it running?')
    sys.exit(1)
#
# Call the DBus method Hello and print the return value.
# print(proxy.GetJobStatus('$test'))
