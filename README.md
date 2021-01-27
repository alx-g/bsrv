# Borg Backup Service (bsrv)

## Daemon

`bsrvd` is a Python3 daemon that schedules and runs borg backups (in push mode) automatically.

## CLI

`bsrvcli` can be used to retrieve status infos and control the daemon's behavior manually.

## Tray Symbol

`bsrvtray` connects to the daemon via DBus, gives a status overview and allows similar functionality to the cli client from a tray menu

## Status Service

`bsrvstatd` is a Python3 daemon that periodically checks the backup repositories for the latest backup archives. It may trigger external commands, e.g. to inform daily or only in case of failed backups.

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
* **texttable**
* **pyqt5** (only necessary for `bsrvtray`)

## Installation

`bsrvd`, at least for now, is hosted on a custom repository: https://pip.alx-g.de
To install it using pip directly, use the following command:
```
pip install --extra-index-url https://pip.alx-g.de/ bsrv
```

## Configuration file

The default path to the config file for `bsrvd` and `bsrvstatd` is `/etc/bsrvd.conf`.
A different config file can be supplied with the `-c` argument.

### Schedule syntax

The syntax somewhat loosely follows crontab notation.
In general, there are two ways to specify a schedule:

#### 1. **Relative** scheduling
   
This schedules the next event based on a reference time **TREF**, which is normally the point in time the last event occured.

| Alias | Description |
|---|---|
|`@weekly`|Run as soon as **TREF** lies back more than 1 week
|`@daily`|Run as soon as **TREF** lies back more than 1 day
|`@hourly`|Run as soon as **TREF** lies back more than 1 hour
|`@every [TIMEPERIOD]`|Run as soon as **TREF** lies back more than `[TIMEPERIOD]`

`[TIMEPERIOD]` is a string defining a period in time with a list of one or more integers, each followed by one of the following units:

`week` or `weeks` or `w`,

`day` or `days` or `d`,

`hour` or `hours` or `h`,

`minute` or `minutes` or `m`.

**Examples**

| Example | Description |
|---|---|
| `@every  1minute`| Run as soon as **TREF** lies back more than 1 minute
| `@every 1 week 1 day 1 hour 1 minute` | Run as soon as **TREF** lies back more than 1 week, 1 day, 1 hour, and 1 minute
| `@every 1w1d1h1m` | Same thing
| `@hourly` | Run as soon as **TREF** lies back more than 1 hour
| `@every 2 hours` | Run as soon as **TREF** lies back more than 2 hours

#### 2. **Absolute** scheduling

This schedules the next event based on system time.
The format consists of 5 space-separated columns, each obeying the following syntax:

`SPEC[/DIVISOR]`

where `SPEC` is a comma separated list of integers or ranges indicated with a `-` or alternatively, an `*`.
`DIVISOR` is an integer.

`SPEC` defines the values considered, `DIVISOR` limits these values to the ones divisible by it.
`*` indicates to consider all possible values.

```
  minute  hour        day(month)  month   day(week)
  *       *           *           *       *           -> Run every minute
  *       *           1           1       *           -> Run every minute on January 1st
  0       *           *           *       *           -> Run every full hour
  0       8-12,16-17  *           *       *           -> Run at full hours 8,9,10,11,12,16,17
  */10    *           *           *       *           -> Run when minutes divisible by 10
  0       8           */10        *       *           -> Run when (day of month)-1 divisible by 10 and time is 8:00
  0       6           *           */2     0           -> Run when month-1 is divisible by 2, weekday is sunday and time is 6:00
  0       8-15        *           *       *           -> Run every day at 8:00,9:00,10:00,11:00,12:00,13:00,14:00, and 15:00
```

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
They are now available in this virtual environment as `bsrvd`, `bsrvcli`, `bsrvtray`, `bsrvstatd`.
