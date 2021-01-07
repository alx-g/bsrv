import datetime
import signal

from dasbus.connection import SessionMessageBus
from dasbus.identifier import DBusServiceIdentifier
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.signal import Signal
from dasbus.typing import Str, List, Dict, Bool, Int

from .logger import Logger
from .job import Scheduler

SESSION_BUS = SessionMessageBus()

SERVICE_IDENTIFIER = DBusServiceIdentifier(
    namespace=("de", "alxg", "borgsrvd"),
    message_bus=SESSION_BUS
)


@dbus_interface(SERVICE_IDENTIFIER.interface_name)
class DBusInterface(object):
    def __init__(self, scheduler):
        self.scheduler = scheduler
        super(DBusInterface, self).__init__()

    @dbus_signal
    def StatusUpdateNotifier(self, job_name: Str, scheduler_status: Str, retry: Int):
        pass

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

    def MountRepo(self, job_name: Str) -> Str:
        job = self.scheduler.find_job_by_name(job_name)
        if not job:
            return ''
        else:
            if job.mount():
                return job.mount_dir
            else:
                return ''

    def UMountRepo(self, job_name: Str) -> Bool:
        job = self.scheduler.find_job_by_name(job_name)
        if not job:
            return False
        else:
            return job.umount()

    def Shutdown(self):
        Logger.info('Received Shutdown command via DBus')
        self.exit_signal.emit()


class MainLoop:
    def __init__(self, scheduler: Scheduler):
        self.interface = DBusInterface(scheduler=scheduler)
        self.scheduler = scheduler
        self.scheduler.status_update_callback = self.__status_update_handler
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

    def __status_update_handler(self, job_name: str, scheduler_status: str, retry: int):
        self.interface.StatusUpdateNotifier(job_name, scheduler_status, retry)

    def stop(self):
        self.loop.quit()
