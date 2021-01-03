#!/usr/bin/env python3
import time

from borgsrv import Config, Logger, Job, Scheduler

try:

    # Initialize primitive logging
    Logger.initialize()

    # Initialize Config
    Config.initialize('default.ini')

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

except SystemExit as e:
    if e.code == 0:
        Logger.info('Clean Exit.')
    else:
        Logger.error('Exit ({})'.format(e.code))
else:

    try:
        scheduler.start()
        time.sleep(1000000)

    except SystemExit as e:
        if e.code == 0:
            Logger.info('Clean Exit.')
        else:
            Logger.error('Exit ({})'.format(e.code))
    except KeyboardInterrupt:
        Logger.info('User requested exit')
    finally:
        scheduler.stop()