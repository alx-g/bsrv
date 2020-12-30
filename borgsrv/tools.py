import json
import dateutil.parser


def parse_json(json_source):
    source = json.loads(json_source)
    return datetime_json(source)


def datetime_json(source):
    for k, v in source.items():
        if isinstance(v, list):
            for a in v:
                datetime_json(a)
        elif isinstance(v, dict):
            datetime_json(v)
        elif isinstance(v, str) and not v.isdigit():
            try:
                float(v)
                continue
            except ValueError:
                pass
            try:
                source[k] = dateutil.parser.parse(v, ignoretz=True)
            except (ValueError, OverflowError):
                pass

    return source
