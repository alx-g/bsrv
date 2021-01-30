#!/usr/bin/env python
import logging
import os
import sys
import argparse
from pkg_resources import resource_filename
from typing import Dict

from PyQt5.QtCore import QTimer, QMutex, QMutexLocker
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from dasbus.error import DBusError

from bsrv import SYSTEM_BUS, SESSION_BUS, get_dbus_service_identifier

DATA_PACKAGE_NAME = 'bsrv'


class Status:
    OK = 0
    RUNNING = 1
    PAUSE = 2
    WARNING = 3
    ERROR = 4
    NO_CONNECTION = 99


class MainApp:
    def __init__(
            self,
            qapp,
            dbus_service_identifier
    ):
        self.proxy = None

        self.log = logging.getLogger()
        log_formatter = logging.Formatter("%(asctime)s [%(levelname)8.8s] %(message)s", datefmt="%Y-%m-%d %H-%M-%S")
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(log_formatter)
        self.log.addHandler(stdout_handler)
        self.log.setLevel(logging.DEBUG)

        # Reference to main PyQt.QApplication
        self.qapp: QApplication = qapp

        # Save reference to dbus interface identifier
        self.dbus_service_identifier = dbus_service_identifier

        self.log.critical(resource_filename(DATA_PACKAGE_NAME, "icons/icon_noconnection.png"))

        # Load all tray icon files
        self.icon_noconnection = [
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_noconnection.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon.png"))
        ]
        self.icon_pause = [
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_pause.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon.png"))
        ]
        self.icon_running = [
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running0.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running1.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running2.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running3.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running4.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running5.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running6.png")),
            QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_running7.png"))
        ]
        self.icon_error = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_error.png"))
        self.icon_ok = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_ok.png"))
        self.icon_attention = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/icon_attention.png"))

        # Load icons for menu
        self.micon_exit = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_exit.png"))
        self.micon_pause = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_pause.png"))
        self.micon_info = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_info.png"))
        self.micon_run = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_run.png"))
        self.micon_mount = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_mount.png"))
        self.micon_umount = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_umount.png"))
        # self.micon_log = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_log.png"))
        # self.micon_console = QIcon(resource_filename(DATA_PACKAGE_NAME, "icons/micon_console.png"))

        # Setup tray icon
        self.qapp.setQuitOnLastWindowClosed(False)
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icon_noconnection[0])

        # Create right-click menu for tray
        self.menu = QMenu()

        self.exit_action = QAction("Exit", self.qapp)
        self.exit_action.triggered.connect(self.__click_exit)
        self.exit_action.setIcon(self.micon_exit)
        self.menu.addAction(self.exit_action)
        self.menu.addSeparator()

        self.pause_action = QAction("Toggle Pause", self.qapp)
        self.pause_action.triggered.connect(self.__click_pause)
        self.pause_action.setIcon(self.micon_pause)
        self.menu.addAction(self.pause_action)
        self.menu.addSeparator()

        self.tray.setContextMenu(self.menu)

        # Display tray icon
        self.tray.setVisible(True)

        self.status: int = Status.NO_CONNECTION

        self.job_mutex = QMutex()
        self.job_status: Dict[str, int] = {}
        self.job_submenu: Dict[str, QMenu] = {}
        self.job_actions: Dict[str, Dict[str, QAction]] = {}

        self.animation_timer = QTimer()
        self.animation_timer.setInterval(200)
        self.animation_timer.timeout.connect(self.update_icon)
        self.animation_counter = 0

        self.log.info('Start')

        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.setInterval(30000)
        self.heartbeat_timer.timeout.connect(self.heartbeat)
        self.heartbeat()

        self.animation_timer.start()
        self.heartbeat_timer.start()

    def update_icon(self):
        with QMutexLocker(self.job_mutex):

            if self.job_status.values():
                sum_status = max(self.job_status.values())
            else:
                sum_status = Status.WARNING

            icon_status = max(sum_status, self.status)
            if icon_status == Status.NO_CONNECTION:
                self.tray.setIcon(self.icon_noconnection[(self.animation_counter // 2) % len(self.icon_noconnection)])
            if icon_status == Status.PAUSE:
                ctr = (self.animation_counter // 2) % 4
                if ctr > 1:
                    ctr = 0
                self.tray.setIcon(self.icon_pause[ctr])
            elif icon_status == Status.OK:
                self.tray.setIcon(self.icon_ok)
            elif icon_status == Status.WARNING:
                self.tray.setIcon(self.icon_attention)
            elif icon_status == Status.ERROR:
                self.tray.setIcon(self.icon_error)
            elif icon_status == Status.RUNNING:
                self.tray.setIcon(self.icon_running[self.animation_counter % len(self.icon_running)])
            self.animation_counter += 1

            for job, job_status in self.job_status.items():
                if job_status == Status.OK:
                    self.job_submenu[job].setIcon(self.icon_ok)
                elif job_status == Status.RUNNING:
                    self.job_submenu[job].setIcon(self.icon_running[0])
                elif job_status == Status.WARNING:
                    self.job_submenu[job].setIcon(self.icon_attention)
                elif job_status == Status.ERROR:
                    self.job_submenu[job].setIcon(self.icon_error)

    def __add_job(self, job_name: str):
        self.log.info('Add job {}'.format(job_name))
        job_menu = QMenu("Job {}".format(job_name), parent=self.menu)

        job_mount_action = QAction("Mount", parent=job_menu)
        job_umount_action = QAction("UMount", parent=job_menu)
        job_list_action = QAction("List", parent=job_menu)
        job_run_action = QAction("Run Now", parent=job_menu)

        job_mount_action.setIcon(self.micon_mount)
        job_umount_action.setIcon(self.micon_umount)
        job_list_action.setIcon(self.micon_info)
        job_run_action.setIcon(self.micon_run)

        job_mount_action.triggered.connect(lambda: self.__click_mount(job_name))
        job_umount_action.triggered.connect(lambda: self.__click_umount(job_name))
        job_list_action.triggered.connect(lambda: self.__click_list(job_name))
        job_run_action.triggered.connect(lambda: self.__click_run(job_name))

        job_menu.addAction(job_run_action)
        job_menu.addAction(job_list_action)
        job_menu.addAction(job_mount_action)
        job_menu.addAction(job_umount_action)

        job_menu_action = self.menu.addMenu(job_menu)

        self.job_submenu[job_name] = job_menu
        self.job_actions[job_name] = {
            'mount': job_mount_action,
            'umount': job_umount_action,
            'list': job_list_action,
            'run': job_run_action,
            'menu': job_menu_action
        }
        self.job_status[job_name] = Status.ERROR

    def __del_job(self, job_name: str):
        self.log.info('Delete job {}'.format(job_name))
        self.job_submenu[job_name].removeAction(self.job_actions[job_name]['mount'])
        self.job_submenu[job_name].removeAction(self.job_actions[job_name]['umount'])
        self.job_submenu[job_name].removeAction(self.job_actions[job_name]['list'])
        self.job_submenu[job_name].removeAction(self.job_actions[job_name]['run'])
        self.menu.removeAction(self.job_actions[job_name]['menu'])
        del self.job_actions[job_name]
        del self.job_submenu[job_name]
        del self.job_status[job_name]

    def __click_mount(self, job_name: str):
        self.log.info('Click mount for job {}'.format(job_name))
        try:
            if not self.proxy.MountRepo(job_name):
                self.log.error('Could not mount job {}'.format(job_name))
        except DBusError:
            self.proxy = None
            self.status = Status.NO_CONNECTION
            self.log.error('Could not mount job {}'.format(job_name))

    def __click_umount(self, job_name: str):
        self.log.info('Click umount for job {}'.format(job_name))
        try:
            if not self.proxy.UMountRepo(job_name):
                self.log.error('Could not mount job {}'.format(job_name))
        except DBusError:
            self.proxy = None
            self.status = Status.NO_CONNECTION
            self.log.error('Could not mount job {}'.format(job_name))

    def __click_run(self, job_name: str):
        self.log.info('Click run for job {}'.format(job_name))
        try:
            if not self.proxy.RunJob(job_name):
                self.log.error('Could not run job {}'.format(job_name))
        except DBusError:
            self.proxy = None
            self.status = Status.NO_CONNECTION
            self.log.error('Could not run job {}'.format(job_name))

    def __click_list(self, job_name: str):
        self.log.info('Click list for job {}. Not implemented!'.format(job_name))
        pass

    def __click_pause(self):
        self.log.info('Click pause toggle button.')
        try:
            if self.proxy:
                self.proxy.SetPause(not self.proxy.GetPause())
        except DBusError:
            self.proxy = None
            self.status = Status.NO_CONNECTION
            self.log.error('Could not toggle pause.')

    def heartbeat(self):
        self.log.info('[Heartbeat] Triggered')
        if self.proxy is None:
            self.log.info('[Heartbeat] Not connected yet')
            try:
                self.proxy = self.dbus_service_identifier.get_proxy()
                self.log.info('[Heartbeat] Created proxy obj')
            except DBusError:
                self.proxy = None
                self.status = Status.NO_CONNECTION
                self.log.warning('[Heartbeat] Proxy creation failed')

        if self.proxy is not None:
            self.log.info('[Heartbeat] Connection exists')
            try:
                server_jobs = set(self.proxy.GetLoadedJobs())

                if self.__status_update not in self.proxy.StatusUpdateNotifier._callbacks:
                    self.proxy.StatusUpdateNotifier.connect(self.__status_update)
                if self.__pause not in self.proxy.PauseNotifier._callbacks:
                    self.proxy.PauseNotifier.connect(self.__pause)

                if self.proxy.GetPause():
                    self.status = Status.PAUSE
                else:
                    self.status = Status.OK

            except DBusError:
                self.proxy = None
                self.status = Status.NO_CONNECTION
                server_jobs = set([])
                self.log.error('[Heartbeat] DBusError while executing GetLoadedJobs()')

            cur_jobs = set(self.job_status.keys())

            jobs_to_del = cur_jobs - server_jobs
            jobs_to_add = server_jobs - cur_jobs

            with QMutexLocker(self.job_mutex):
                for job_name in jobs_to_del:
                    self.__del_job(job_name)
                for job_name in jobs_to_add:
                    self.__add_job(job_name)

                for job_name in self.job_status.keys():
                    try:
                        job_s = self.proxy.GetJobStatus(job_name)
                    except DBusError:
                        self.proxy = None
                        self.status = Status.NO_CONNECTION
                        self.log.error('[Heartbeat] DBusError while initializing job status using GetJobStatus()')
                        return
                    sched = job_s['schedule_status']
                    retry = int(job_s['job_retry'])
                    self.__store_status(job_name, sched, retry)

    def __status_update(self, job_name: str, sched: str, retry: int):
        self.log.info(
            '[update_notfication] Notified by server: job_name: {}, sched: {}, retry: {}'.format(job_name, sched,
                                                                                                 retry))
        with QMutexLocker(self.job_mutex):
            if job_name not in self.job_status.keys():
                self.log.info('[update_notfication] job {} does not exist??'.format(job_name))
                return
            else:
                self.__store_status(job_name, sched, retry)

    def __pause(self, is_paused: bool):
        if is_paused:
            self.status = Status.PAUSE
        else:
            self.status = Status.OK

    def __store_status(self, job_name: str, sched: str, retry: int):
        if sched == 'running':
            self.job_status[job_name] = Status.RUNNING
        elif sched == 'next' or sched == 'wait':
            if retry == 0:
                self.job_status[job_name] = Status.OK
            elif retry < 0:
                self.job_status[job_name] = Status.ERROR
            else:
                self.job_status[job_name] = Status.WARNING
        else:
            self.job_status[job_name] = Status.ERROR

    @staticmethod
    def __click_exit():
        exit()


def main():
    parser = argparse.ArgumentParser(description='bsrv tray icon')
    parser.add_argument('--session-bus', action='store_true', default=False,
                        help='Connect to daemon dbus interface via SESSION_BUS, default is SYSTEM_BUS')

    args = parser.parse_args()

    if args.session_bus:
        service_identifier = get_dbus_service_identifier(SESSION_BUS)
    else:
        service_identifier = get_dbus_service_identifier(SYSTEM_BUS)

    script_dir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(script_dir)

    # Create main Application
    qapp = QApplication(sys.argv)

    # Variable is necessary, otherwise the object will be cleared by garbage collection!
    mapp = MainApp(qapp=qapp, dbus_service_identifier=service_identifier)

    # Run event loop
    sys.exit(qapp.exec_())


if __name__ == '__main__':
    main()
