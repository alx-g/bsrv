#!/usr/bin/env python3
import argparse
import json
import sys
import time

from dasbus.error import DBusError

from bsrv import SYSTEM_BUS, SESSION_BUS, get_dbus_service_identifier
from bsrv.tools import parse_json, pretty_info


def main():
    parser = argparse.ArgumentParser(description='Borg service CLI')

    m_group = parser.add_mutually_exclusive_group()
    m_group.add_argument('-l', '--list-jobs', action='store_true', default=False, help='List names of loaded jobs.')
    m_group.add_argument('-i', '--info', metavar='JOB_NAME', default=None, action='store', type=str,
                         help='Display information about the job, including last archive dates, repository size and scheduling status')
    m_group.add_argument('-r', '--run', metavar='JOB_NAME', default=None, action='store', type=str,
                         help='Manually run a job now. This may have an influence on future scheduled actions for this job.')
    m_group.add_argument('-m', '--mount', metavar='JOB_NAME', action='store', default=None, type=str,
                         help='Mount repository for given job using "borg mount"')
    m_group.add_argument('-u', '--umount', metavar='JOB_NAME', action='store', default=None, type=str,
                         help='UMount repository for given job using "borg umount"')
    m_group.add_argument('--pause', action='store_true', default=False,
                         help='Pause scheduler. No jobs will be run until scheduler is unpaused.')
    m_group.add_argument('--unpause', action='store_true', default=False,
                         help='Unpause scheduler. (see --pause for info)')
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
        elif args.info:
            info_json = proxy.GetJobInfo(args.info)
            if info_json:
                if args.json:
                    print(info_json)
                else:
                    info = parse_json(info_json)
                    print(pretty_info(info))

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
        elif args.pause:
            proxy.SetPause(True)
        elif args.unpause:
            proxy.SetPause(False)

    except DBusError as e:
        print('Could not connect to daemon, is it running?')
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
