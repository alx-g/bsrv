# Borg Backup Service (bsrv)

## Daemon

`bsrvd` is a Python3 daemon that schedules and runs borg backups (in push mode) automatically.

## CLI

`bsrvcli` can be used to retrieve status infos and control the daemon's behavior manually.

## Tray Symbol

`bsrvtray` connects to the daemon via DBus, gives a status overview and allows similar functionality to the cli client from a tray menu

## Dependencies

### System

To be able to install the python dependencies, `gobject-introspection` needs to be present.

* **Fedora, CentOS, RHEL, etc.**: gobject-introspection-devel
* **Debian, Ubuntu, Mint, etc.**: libgirepository1.0-dev
* **Arch**: gobject-introspection
* **FreeBSD**: gobject-introspection
* **Cygwin**: libgirepository1.0-devel
* **msys2**: mingw-w64-x86_64-gobject-introspection and/or mingw-w64-i686-gobject-introspection

Also, the service relies on `dbus` to provide the interface for `bsrvcli` and other clients.

### Python

* **dasbus**
* **pygobject**
* **systemd-logging**
* **pyqt5** (only necessary for `bsrvtray`)

## Development environment setup

Create a new virtual environment, e.g with:
```
python3 -m venv venv/
```
Enter the environment with:
```
source venv/bin/activate
```
Use pip to install the entry point scripts in editable mode:
```
pip install -e .
```
They are now available in this virtual environment as `bsrvd` and `bsrvcli`.
