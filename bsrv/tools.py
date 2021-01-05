import datetime
import json
from typing import Dict


def parse_json(json_source):
    source = json.loads(json_source)
    return json_iso2datetime(source)


def gen_json(obj: Dict):
    obj = json_datetime2iso(obj)
    return json.dumps(obj)


def json_datetime2iso(obj):
    for k, v in obj.items():
        if isinstance(v, list):
            for a in v:
                json_datetime2iso(a)
        elif isinstance(v, dict):
            json_datetime2iso(v)
        elif isinstance(v, datetime.datetime):
            obj[k] = v.isoformat()
    return obj


def json_iso2datetime(source):
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
