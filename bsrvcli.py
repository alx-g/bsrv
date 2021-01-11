#!/usr/bin/env python3
import argparse
import json
import sys
import time

from dasbus.error import DBusError

from bsrv import SYSTEM_BUS, SESSION_BUS, get_dbus_service_identifier


def main():
    parser = argparse.ArgumentParser(description='Borg service CLI')

    m_group = parser.add_mutually_exclusive_group()
    m_group.add_argument('-l', '--list-jobs', action='store_true', default=False, help='List names of loaded jobs.')
    m_group.add_argument('-s', '--status', metavar='JOB_NAME', default=None, action='store', type=str,
                         help='Display status of job with given name.')
    m_group.add_argument('-r', '--run', metavar='JOB_NAME', default=None, action='store', type=str,
                         help='Manually run a job now. This may have an influence on future scheduled actions for this job.')
    m_group.add_argument('-m', '--mount', metavar='JOB_NAME', action='store', default=None, type=str,
                         help='Mount repository for given job using "borg mount"')
    m_group.add_argument('-u', '--umount', metavar='JOB_NAME', action='store', default=None, type=str,
                         help='UMount repository for given job using "borg umount"')
    m_group.add_argument('--shutdown', action='store_true', default=False, help='Shutdown daemon')

    parser.add_argument('--session-bus', action='store_true', default=False,
                        help='Connect to daemon dbus interface via SESSION_BUS, default is SYSTEM_BUS')

    parser.add_argument('--json', action='store_true', default=False,
                        help='Instead of outputting nicely formatted data, output data as JSON')

    args = parser.parse_args()

    try:
        if args.session_bus:
            service_identifier = get_dbus_service_identifier(SESSION_BUS)
        else:
            service_identifier = get_dbus_service_identifier(SYSTEM_BUS)
        proxy = service_identifier.get_proxy()
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
        elif args.status:
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
                print('| %-53s | %-20s |' % ('Retry counter.', status['job_retry']))
                print('| %-53s | %-20s |' % ('> 0 if last job was successful', ''))
                print('| %-53s | %-20s |' % ('> greater than 0 if last job failed and retries are', ''))
                print('| %-53s | %-20s |' % ('  in progress', ''))
                print('| %-53s | %-20s |' % ('> negative if all retries failed and scheduler gave', ''))
                print('| %-53s | %-20s |' % ('  up', ''))
                print('+' + '-' * 78 + '+')
                print('| %-53s | %-20s |' % ('Scheduling status of this job.', status['schedule_status']))
                print('| %-53s | %-20s |' % ('> running: Currently running.', ''))
                print('| %-53s | %-20s |' % ('> next:    Currently selected for processing at', ''))
                print('| %-53s | %-20s |' % ('           next action time.', ''))
                print('| %-53s | %-20s |' % ('> wait:    Action scheduled at later point in', ''))
                print('| %-53s | %-20s |' % ('           time.', ''))
                print('| %-53s | %-20s |' % ('> none:    No action scheduled for this job. This', ''))
                print('| %-53s | %-20s |' % ('           means no action will ever be run and', ''))
                print('| %-53s | %-20s |' % ('           likely results from invalid', ''))
                print('| %-53s | %-20s |' % ('           configuration.', ''))
                print('+' + '-' * 78 + '+')
                print('| %-53s | %-20s |' % ('Next action time for this job', status['schedule_dt']))
                print('+' + '=' * 78 + '+')
        elif args.run:
            if not proxy.RunJob(args.run):
                sys.exit(1)
        elif args.mount:
            ret = proxy.MountRepo(args.mount)
            if not ret:
                sys.exit(1)
            else:
                print(ret)
        elif args.umount:
            if not proxy.UMountRepo(args.umount):
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

    except DBusError as e:
        print('Could not connect to daemon, is it running?')
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
