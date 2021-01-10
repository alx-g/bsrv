import os
from typing import Any, Union

from .config import Config
from .logger import Logger
from .tools import parse_json, gen_json


class Cache:
    data = None
    file = None

    @staticmethod
    def initialize():
        base_dir = Config.get('borg', 'base_dir')
        Cache.file = os.path.join(base_dir, 'bsrvd.cache')
        try:
            with open(Cache.file, 'r') as f:
                cnt = f.read()
                Cache.data = parse_json(cnt)
        except FileNotFoundError:
            Cache.data = {}

    @staticmethod
    def get(key: str) -> Union[None, Any]:
        if Cache.data is None:
            raise RuntimeError('Cache was never initialized')
        try:
            return Cache.data[key]
        except KeyError:
            return None

    @staticmethod
    def set(key: str, value: Any):
        if Cache.data is None:
            raise RuntimeError('Cache was never initialized')
        Cache.data[key] = value
        try:
            with open(Cache.file, 'w') as f:
                cnt = gen_json(Cache.data)
                f.write(cnt)
        except:
            Logger.error('Could not write cache file "{}".'.format(Cache.file))
