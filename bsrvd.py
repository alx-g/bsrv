#!/usr/bin/env python3
import argparse

from bsrv import Config, Logger, Job, Scheduler, MainLoop, Cache, SESSION_BUS, SYSTEM_BUS


def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description='Borg Service daemon.')
    parser.add_argument('-c', metavar='CONFIGFILE', action='store', default='/etc/bsrvd.conf', type=str,
                        help='Path to configuration file.')
    parser.add_argument('--session-bus', action='store_true', default=False,
                        help='Use SESSION_BUS to publish dbus interface. Default is SYSTEM_BUS.')

    args = parser.parse_args()

    try:

        # Initialize primitive logging
        Logger.initialize()

        # Initialize Config
        Config.initialize(args.c)

        # Configure proper logging according to config
        Logger.configure()

        # Make sure all working directories exist and have proper permissions
        Config.check_dirs()

        # Instantiate scheduler
        scheduler = Scheduler()

        # Initialize Cache
        Cache.initialize()

        # Extract Jobs from Config
        for s in Config.sections():
            if s[0] == ':':
                newjob = Job.from_config(s)
                if newjob:
                    scheduler.register(newjob)

        if args.session_bus:
            loop = MainLoop(scheduler=scheduler, bus=SESSION_BUS)
        else:
            loop = MainLoop(scheduler=scheduler, bus=SYSTEM_BUS)

    except SystemExit as e:
        if e.code == 0:
            Logger.info('Clean Exit.')
        else:
            Logger.critical('Exit ({})'.format(e.code))
    else:

        try:
            scheduler.start()
            loop.start()

        except SystemExit as e:
            if e.code == 0:
                Logger.info('Clean Exit.')
            else:
                Logger.critical('Exit ({})'.format(e.code))
        except KeyboardInterrupt:
            Logger.info('User requested exit')
        finally:
            scheduler.stop()


if __name__ == '__main__':
    main()
