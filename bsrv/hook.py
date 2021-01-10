import shlex
import subprocess
import threading
from typing import Union, NoReturn, List, TYPE_CHECKING

from .logger import Logger

if TYPE_CHECKING:
    from .job import Job


class Hook:
    def __init__(self, name: str, command_string: str, timeout: int):
        self.parent: Union[None, 'Job'] = None
        self.name: str = name
        self.command: List[str] = shlex.split(command_string)
        self.timeout: int = timeout
        self.task: Union[None, 'subprocess.Popen'] = None

    def set_parent(self, job: 'Job'):
        self.parent = job

    def trigger(self) -> NoReturn:
        if self.command:
            Logger.info('Triggered hook "{}" for job "{}"'.format(self.name, self.parent.name))
            new_thread = threading.Thread(target=self.run_thread)
            new_thread.start()

    def run_thread(self) -> NoReturn:
        try:
            self.task = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            Logger.error('Exception occured during Popen: {}'.format(str(e)))
            return

        try:
            stdout, stderr = self.task.communicate(timeout=self.timeout)
            stdout_ = stdout.decode()
            stderr_ = stderr.decode()
            if self.task.returncode == 0:
                Logger.info('Hook "{}" for job "{}" succeeded'.format(self.name, self.parent.name))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.info('[HOOK] ' + line)
            else:
                Logger.error('Hook "{}" for job "{}" failed with code {}: {}'.format(self.name, self.parent.name,
                                                                                     self.task.returncode,
                                                                                     str(self.command)))
                if stdout_ or stderr_:
                    for line in (stdout_ + stderr_).splitlines(keepends=False):
                        Logger.error('[HOOK] ' + line)

        except subprocess.TimeoutExpired:
            Logger.error(
                'Hook "{}" for job "{}" timed out after {} s'.format(self.name, self.parent.name, self.timeout))
