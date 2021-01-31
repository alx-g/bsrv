import datetime
import json
import math
from typing import Union

from texttable import Texttable


def parse_json(json_source: str):
    source = json.loads(json_source)
    return json_iso2datetime(source)


def gen_json(obj: dict):
    obj = json_datetime2iso(obj)
    return json.dumps(obj)


def json_datetime2iso(obj: dict):
    for k, v in obj.items():
        if isinstance(v, list):
            for a in v:
                json_datetime2iso(a)
        elif isinstance(v, dict):
            json_datetime2iso(v)
        elif isinstance(v, datetime.datetime):
            obj[k] = v.isoformat()
    return obj


def json_iso2datetime(source: dict):
    for k, v in source.items():
        if isinstance(v, list):
            for a in v:
                json_iso2datetime(a)
        elif isinstance(v, dict):
            json_iso2datetime(v)
        elif isinstance(v, str) and not v.isdigit():
            try:
                float(v)
                continue
            except ValueError:
                pass
            try:
                source[k] = datetime.datetime.fromisoformat(v)
            except (ValueError, OverflowError):
                pass

    return source


def pretty_datetime(dt: Union[datetime.datetime, str]):
    if not isinstance(dt, datetime.datetime):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except:
            return 'None'
    try:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return 'None'


def pretty_size(sz: int):
    names = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
    idx = math.floor(math.log(sz, 1024))
    sz = sz / math.pow(1024, idx)
    if idx == 0:
        return '%d %s' % (int(sz), names[idx])
    else:
        return '%.1f %s' % (sz, names[idx])


def pretty_info(info: dict):
    out = ''
    out += 'Scheduler info about this job:\n'

    tbl = Texttable(max_width=80)
    tbl.header(['Description', 'Value'])
    tbl.set_cols_align(['l', 'c'])
    tbl.add_row(['Time of last successful borg archive', pretty_datetime(info['scheduler']['job_last_successful'])])
    tbl.add_row(['Time of next suggested borg archive', pretty_datetime(info['scheduler']['job_next_suggested'])])
    tbl.add_row(['Retry counter (0: success, >0: retry, <0: gave up)', info['scheduler']['job_retry']])
    tbl.add_row(['Scheduling status of this job', info['scheduler']['schedule_status']])
    tbl.add_row(['Next action time for this job', pretty_datetime(info['scheduler']['schedule_dt'])])
    out += tbl.draw() + '\n\n'

    out += 'The Repository for this job contains the following archives:\n'
    tbl = Texttable(max_width=80)
    tbl.header(['Name', 'Start', 'Time'])
    for archive in info['archives']:
        tbl.add_row([archive['name'], pretty_datetime(archive['start']), pretty_datetime(archive['time'])])
    out += tbl.draw() + '\n\n'

    out += 'Repository stats:\n'
    tbl = Texttable(max_width=80)
    tbl.header(['Name', 'Value'])
    tbl.set_cols_align(['l', 'c'])
    tbl.add_row(['Original Size', pretty_size(int(info['cache']['stats']['total_size']))])
    tbl.add_row(['Compressed Size', pretty_size(int(info['cache']['stats']['total_csize']))])
    tbl.add_row(['Deduplicated Size', pretty_size(int(info['cache']['stats']['unique_csize']))])
    tbl.add_row(['Total Chunks', str(info['cache']['stats']['total_chunks'])])
    tbl.add_row(['Unique Chunks', str(info['cache']['stats']['total_unique_chunks'])])
    out += tbl.draw()

    return out
