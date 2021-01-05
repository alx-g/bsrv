#!/usr/bin/env python3
import argparse

from bsrv import Config, Logger, Job, Scheduler, MainLoop

# Argument parsing
parser = argparse.ArgumentParser(description='Borg Service daemon.')
parser.add_argument('-c', metavar='CONFIGFILE', action='store', default='/etc/bsrvd.conf', type=str,
                    help='Path to configuration file.')

args = parser.parse_args()

try:

    # Initialize primitive logging
    Logger.initialize()

    Logger.info('Startup.')

    # Initialize Config
    Config.initialize(args.c)

    # Configure proper logging according to config
    Logger.configure()

    # Instantiate scheduler
    scheduler = Scheduler()

    # Extract Jobs from Config
    for s in Config.sections():
        if s[0] == '$':
            newjob = Job.from_config(s)
            if newjob:
                scheduler.register(newjob)

    # setup DBUS interface
    loop = MainLoop(scheduler=scheduler)

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
