import os
import shlex
import subprocess
import threading
from typing import Union, NoReturn, List, TYPE_CHECKING

from .logger import Logger
from .demote import DemotionSubprocess
from .config import Config

if TYPE_CHECKING:
    pass


class Hook:
    @staticmethod
    def from_config(cfg_section: str, name: str):
        command_str = Config.get(cfg_section, name, fallback=Config.get('borg', name, fallback=''))
        timeout = Config.getint(cfg_section, name + '_timeout', fallback=Config.getint('borg', name + '_timeout',
                                                                                       fallback=Config.getint('borg',
                                                                                                              'hook_timeout',
                                                                                                              fallback=20)))
        run_as = Config.get(cfg_section, name + '_run_as', fallback=Config.get('borg', name + '_run_as', fallback=None))
        return Hook(name=name, command_string=command_str, timeout=timeout, run_as=run_as)

    def __init__(self, name: str, command_string: str, timeout: int, run_as: Union[str, None]):
        self.parent_descr: Union[str, None] = None
        self.name: str = name
        self.command: List[str] = shlex.split(command_string)
        self.timeout: int = timeout
        self.task: Union[None, 'subprocess.Popen'] = None
        self.demotion = DemotionSubprocess(run_as, parent_descr='Hook:{}'.format(self.name))

    def set_parent_description(self, parent_descr: str):
        self.parent_descr = parent_descr

    def trigger(self, env: dict = None) -> NoReturn:
        if self.command:
            Logger.info('Triggered hook "{}" for "{}"'.format(self.name, self.parent_descr))
            new_thread = threading.Thread(target=self.run_thread, args=(env,))
            new_thread.start()

    def trigger_wait(self, env: dict = None) -> NoReturn:
        if self.command:
            Logger.info('Triggered hook "{}" for "{}"'.format(self.name, self.parent_descr))
            self.run_thread(env)

    def run_thread(self, env: dict = None) -> NoReturn:
        try:
            proc_env = os.environ.copy()
            proc_env['BSRV_HOOK_NAME'] = self.name
            if env:
                for key, val in env.items():
                    proc_env[key] = val
            self.task = self.demotion.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=proc_env)
        except Exception as e:
            Logger.error('Exception occured during Popen: {}'.format(str(e)))
            return

        try:
            stdout, stderr = self.task.communicate(timeout=self.timeout)
            stdout_ = stdout.decode()
            stderr_ = stderr.decode()
            if self.task.returncode == 0:
                Logger.info('Hook "{}" for "{}" succeeded'.format(self.name, self.parent_descr))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.info('[HOOK] ' + line)
            else:
                Logger.error('Hook "{}" for "{}" failed with code {}: {}'.format(self.name, self.parent_descr,
                                                                                 self.task.returncode,
                                                                                 str(self.command)))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.error('[HOOK] ' + line)

        except subprocess.TimeoutExpired:
            Logger.error(
                'Hook "{}" for "{}" timed out after {} s'.format(self.name, self.parent_descr, self.timeout))
