import os
import shlex
import subprocess
import threading
from typing import Any, Union, NoReturn, List, TYPE_CHECKING

from .logger import Logger

if TYPE_CHECKING:
    pass


class Hook:
    def __init__(self, name: str, command_string: str, timeout: int):
        self.parent: Union[None, Any] = None
        self.name: str = name
        self.command: List[str] = shlex.split(command_string)
        self.timeout: int = timeout
        self.task: Union[None, 'subprocess.Popen'] = None

    def set_parent(self, parent: Any):
        self.parent = parent

    def trigger(self, env: dict = None) -> NoReturn:
        if self.command:
            Logger.info('Triggered hook "{}" for "{}"'.format(self.name, self.parent.name))
            new_thread = threading.Thread(target=self.run_thread, args=(env,))
            new_thread.start()

    def run_thread(self, env: dict = None) -> NoReturn:
        try:
            proc_env = os.environ.copy()
            proc_env['BSRV_HOOK_NAME'] = self.name
            if env:
                for key, val in env.items():
                    proc_env[key] = val
            self.task = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=proc_env)
        except Exception as e:
            Logger.error('Exception occured during Popen: {}'.format(str(e)))
            return

        try:
            stdout, stderr = self.task.communicate(timeout=self.timeout)
            stdout_ = stdout.decode()
            stderr_ = stderr.decode()
            if self.task.returncode == 0:
                Logger.info('Hook "{}" for "{}" succeeded'.format(self.name, self.parent.name))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.info('[HOOK] ' + line)
            else:
                Logger.error('Hook "{}" for "{}" failed with code {}: {}'.format(self.name, self.parent.name,
                                                                                 self.task.returncode,
                                                                                 str(self.command)))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.error('[HOOK] ' + line)

        except subprocess.TimeoutExpired:
            Logger.error(
                'Hook "{}" for "{}" timed out after {} s'.format(self.name, self.parent.name, self.timeout))
