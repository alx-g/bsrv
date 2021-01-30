import datetime
import signal
from typing import TYPE_CHECKING

from dasbus.connection import SessionMessageBus, SystemMessageBus
from dasbus.identifier import DBusServiceIdentifier
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.typing import Str, List, Dict, Bool, Int

from .logger import Logger

if TYPE_CHECKING:
    from .job import Scheduler

SYSTEM_BUS = SystemMessageBus()
SESSION_BUS = SessionMessageBus()

TMP_SERVICE_IDENTIFIER = DBusServiceIdentifier(
    namespace=("de", "alxg", "bsrvd"),
    message_bus=None
)


def get_dbus_service_identifier(message_bus):
    return DBusServiceIdentifier(
        namespace=TMP_SERVICE_IDENTIFIER.namespace,
        message_bus=message_bus
    )


@dbus_interface(TMP_SERVICE_IDENTIFIER.interface_name)
class DBusInterface(object):
    def __init__(self, scheduler):
        self.scheduler = scheduler
        super(DBusInterface, self).__init__()

    @dbus_signal
    def StatusUpdateNotifier(self, job_name: Str, scheduler_status: Str, retry: Int):
        pass

    @dbus_signal
    def PauseNotifier(self, is_paused: Bool):
        pass

    def SetPause(self, is_paused: Bool):
        if is_paused:
            self.scheduler.pause()
        else:
            self.scheduler.unpause()

    def GetPause(self) -> Bool:
        return self.scheduler.paused

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


class MainLoop:
    def __init__(self, scheduler: 'Scheduler', bus=SYSTEM_BUS):
        self.interface = DBusInterface(scheduler=scheduler)
        self.scheduler = scheduler
        self.scheduler.status_update_callback = self.__status_update_handler
        self.scheduler.pause_callback = self.__pause_handler
        self.bus = bus
        self.service_identifier = get_dbus_service_identifier(bus)
        self.loop = EventLoop()

    def start(self):
        self.bus.publish_object(self.service_identifier.object_path, self.interface)
        self.bus.register_service(self.service_identifier.service_name)
        signal.signal(signal.SIGTERM, self.__sigterm_handler)
        try:
            self.loop.run()
        finally:
            self.bus.disconnect()

    def __sigterm_handler(self, signal_number, frame):
        Logger.info('Received SIGTERM')
        self.stop()

    def __status_update_handler(self, job_name: str, scheduler_status: str, retry: int):
        self.interface.StatusUpdateNotifier(job_name, scheduler_status, retry)

    def __pause_handler(self, is_paused: bool):
        self.interface.PauseNotifier(is_paused)

    def stop(self):
        self.loop.quit()
