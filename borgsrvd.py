import datetime

from borgsrv import Config, Logger, Job

try:

    # Initialize primitive logging
    Logger.initialize()

    # Initialize Config
    Config.initialize('default.ini')

    # Configure proper logging according to config
    Logger.configure()

    # Extract Jobs from Config
    jobs = []
    for s in Config.sections():
        if s[0] == '$':
            newjob = Job.from_config(s)
            if newjob:
                jobs.append(newjob)

    if not jobs:
        Logger.warning('No jobs loaded. There is nothing to do.')

    print(jobs[0].schedule.next(datetime.datetime.now()))

except SystemExit as e:
    if e.code == 0:
        Logger.info('Clean Exit.')
    else:
        Logger.error('Exit ({})'.format(e.code))
else:
    Logger.info('Clean Exit.')
