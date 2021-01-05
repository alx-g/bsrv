import datetime
import signal

from dasbus.connection import SessionMessageBus
from dasbus.identifier import DBusServiceIdentifier
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface
from dasbus.signal import Signal
from dasbus.typing import Str, List, Dict, Bool

from .logger import Logger

SESSION_BUS = SessionMessageBus()

SERVICE_IDENTIFIER = DBusServiceIdentifier(
    namespace=("de", "alxg", "borgsrvd"),
    message_bus=SESSION_BUS
)


@dbus_interface(SERVICE_IDENTIFIER.interface_name)
class DBusInterface(object):
    def __init__(self, scheduler, exit_signal):
        self.scheduler = scheduler
        self.exit_signal = exit_signal
        super(DBusInterface, self).__init__()

    def GetLoadedJobs(self) -> List[Str]:
        return [job.name for job in self.scheduler.jobs]

    def GetJobStatus(self, job_name: Str) -> Dict[Str, Str]:
        job = self.scheduler.find_job_by_name(job_name)
        if not job:
            return {}
        else:
            return self.scheduler.get_job_status(job)

    def RunJob(self, job_name: Str) -> Bool:
        job = self.scheduler.find_job_by_name(job_name)
        if not job:
            return False
        else:
            if self.scheduler.advance_to_now(job):
                return True
            else:
                return self.scheduler.schedule(job, datetime.datetime.now())

    def Shutdown(self):
        Logger.info('Received Shutdown command via DBus')
        self.exit_signal.emit()


class MainLoop:
    def __init__(self, scheduler):
        self.exit_signal = Signal()
        self.exit_signal.connect(self.stop)
        self.interface = DBusInterface(scheduler=scheduler, exit_signal=self.exit_signal)
        self.loop = EventLoop()

    def start(self):
        SESSION_BUS.publish_object(SERVICE_IDENTIFIER.object_path, self.interface)
        SESSION_BUS.register_service(SERVICE_IDENTIFIER.service_name)
        signal.signal(signal.SIGTERM, self.__sigterm_handler)
        try:
            self.loop.run()
        finally:
            SESSION_BUS.disconnect()

    def __sigterm_handler(self, signal_number, frame):
        Logger.info('Received SIGTERM')
        self.stop()

    def stop(self):
        self.loop.quit()
