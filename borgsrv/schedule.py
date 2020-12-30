import datetime
import re
from calendar import monthrange


class ScheduleParseError(Exception):
    pass


class Schedule:
    def __init__(self, txt):
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

        self.interval = None
        self.crontab = None

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

    def __parse_cron_elem(self, elem, possible_vals, onebased=False):
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
                vals = [p for p in possible_vals if (p-1) % factor == 0]
            else:
                vals = [p for p in possible_vals if p % factor == 0]

        elif sub_info['all'] is not None:
            vals = possible_vals

        else:
            raise ScheduleParseError('Invalid schedule specification.')

        return vals

    def next(self, last):
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
