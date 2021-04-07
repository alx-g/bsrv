import os
import subprocess
import pwd
from .logger import Logger


class DemotionSubprocess:
    def __init__(self, username: str, parent_descr: str):
        self.parent_descr = parent_descr
        confirmed = False
        if username is not None:
            try:
                pw_record = pwd.getpwnam(username)
                self.uid = pw_record.pw_uid
                self.gid = pw_record.pw_gid

                out = subprocess.check_output(['whoami'], preexec_fn=self.demote_fn(self.uid, self.gid))
                actual_user = out.decode().strip()
                if not actual_user == username:
                    Logger.error('Parent: "{}". Setuid was not successful for user "{}". '
                                 'Process in the future will be run as (uid={},gid={}) '
                                 'instead.'.format(self.parent_descr, username, self.uid, self.gid))
                else:
                    confirmed = True

            except KeyError:
                Logger.error('Parent: "{}". Setuid was not successful for user "{}". '
                             'Process in the future will be run as (uid={},gid={}) '
                             'instead.'.format(self.parent_descr, username, self.uid, self.gid))

            except subprocess.SubprocessError:
                Logger.error('Parent: "{}". Setuid was not successful for user "{}". '
                             'Process in the future will be run as (uid={},gid={}) '
                             'instead.'.format(self.parent_descr, username, self.uid, self.gid))

        if not confirmed:
            self.uid = os.getuid()
            self.gid = os.getgid()

    @staticmethod
    def demote_fn(uid, gid):
        def demote_():
            os.setgid(gid)
            os.setuid(uid)

        return demote_

    def Popen(self, *args, **kwargs):
        return subprocess.Popen(*args, **kwargs, preexec_fn=self.demote_fn(self.uid, self.gid))
