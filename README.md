# Borg Backup Service (bsrv)

**Daemon**

`bsrvd` is a Python3 daemon that schedules and runs borg backups (in push mode) automatically.

**CLI**

`bsrvcli` can be used to retrieve status infos and control the daemon's behavior manually.

**Tray Symbol**

`bsrvtray` connects to the daemon via DBus, gives a status overview and allows similar functionality to the cli client,
but from a tray menu.

**Status Service**

`bsrvstatd` is a Python3 daemon that periodically checks the backup repositories for the latest backup archives.
It may trigger external commands, e.g. to inform daily or only in case of failed backups.

## Dependencies

**System**

To be able to install the python dependencies, `gobject-introspection` needs to be present.

* **Fedora, CentOS, RHEL, etc.**: gobject-introspection-devel
* **Debian, Ubuntu, Mint, etc.**: libgirepository1.0-dev
* **Arch**: gobject-introspection
* **FreeBSD**: gobject-introspection
* **Cygwin**: libgirepository1.0-devel
* **msys2**: mingw-w64-x86_64-gobject-introspection and/or mingw-w64-i686-gobject-introspection

Also, the service relies on `dbus` to provide the interface for `bsrvcli` and other clients.

**Python**

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

After installation, configuration files are needed.
See the following section, and the provided `bsrvd_example.conf` for a guide.

## Configuration

The default path to the config file for `bsrvd` and `bsrvstatd` is `/etc/bsrvd.conf`.
A different config file can be supplied with the `-c` argument.

**Overview**

The configuration file is in **ini** format and should always contain the sections `[logging]` and `[borg]`.
Global options related to `bsrvstatd` are supplied in a `[stat]` section.
Additionally, the file contains *job* sections, defining backups to run or watch.
A job section is defined by assigning it a name with a `:` prefix.

**[logging]**

This section contains configuration options related to logging and are used by both `bsrvd`and `bsrvstatd`.
* `target`: Logging target, select one or more, separate with a comma. Options are as follows:
    * `file`: Log to a rotating file log. Filename and number of logs specified by `path` and `max_logfiles`.
    * `stdout`: Log to stdout.
    * `journald`: Log to systemd's logging daemon. This option can only be used if `bsrvd` is launched via a systemd
        service file.
* `path`: Configure logging path, only used with `target: file`.
* `max_logfiles`: Configure number of daily logs to retain, only used with `target: file`.
* `log_level`: Set logging level, options are: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`.

**[borg]**

This section contains global settings for borg. Also, hooks that should apply to all defined jobs can be defined here.
For more information on hooks, see dedicated section below.

* `binary`: Specify an alternative path to the `borg` binary. If this value is not set, `borg` will be assumed to be in
    **PATH**.
* `base_dir`: Set BORG_BASE_DIR, where borg places its cache and security info (e.g. nonces), default is
    `/var/cache/bsrvd`.
* `mount_dir`: Base directory where to mount borg backup repositories using borg mount, default is `/tmp/bsrvd-mount`.
    The service needs to have write access to this folder.
* `hook_timeout`: Time in seconds, before hook commands in `[borg]` section or in *job* sections are considered to have
    failed. Default is 20 seconds.

The following keys allow the definition of commands to be run when certain events occur.
The commands specified here are used for all jobs. If you wish to specify them individually, you
can use the same keys in a job section to overwrite them. In the following table, all hooks and their purpose are
listed:

| Hook                     | Situation triggering this hook           |
|--------------------------|------------------------------------------|
| `hook_list_failed`       | `borg list` command failed               |
| `hook_list_successful`   | `borg list` command successful           |
| `hook_mount_failed`      | `borg mount`command failed               |
| `hook_mount_successful`  | `borg mount` command successful          |
| `hook_umount_failed`     | `borg umount` command failed             |
| `hook_umount_successful` | `borg umount` command successful         |
| `hook_run_failed`        | Running a backup failed, which means `borg create` or `borg prune` command failed
| `hook_run_successful`    | Running a backup was successful, which means `borg create` and `borg prune` commands succeeded
| `hook_give_up`           | Running a backup failed multiple times until the maximum number of retries was reached and `bsrvd` gave up 

**[stat]**

This section contains the global configuration for `bsrvstatd`.

* `schedule`: Schedule defining when check backup repositories. This is a global setting and results in all jobs being
    checked, if they define a `stat_maxage` key. The syntax of this value is best explained in the
    [Schedule syntax](#schedule-syntax) section. **TREF** is the previously scheduled stat event.
* `hook_timeout`: Time in seconds, before hook commands in `[stat]` section are considered to have failed. Default is
    `60` seconds.
* `hook_satisfied`: Hook command to run when all repositories associated with jobs with `stat_maxage` conditions could
    be reached and they meet their individual conditions.
* `hook_failed`: Hook command to run when any repositories associated with jobs with `stat_maxage` conditions could not
    be reached or they do not meet their individual conditions.

**Job sections [:NAME_HERE]**

Each job section name needs to be prefixed with a `:`. This section contains all information necessary to run a backup
of specified data to a specified repository using borg.

* `borg_repo`: Path to borg repository as it is supplied to the borg command. This may for example include *ssh://* if
    the repository is located on a remote server.
* `borg_passphrase`: Passphrase for this borg repository
* `borg_rsh`: ssh command used to open ssh connection if necessary to connect to repo. Default is `ssh`.
    This is useful to automate the login on a backup server via a certificate. Then, a private key file can be specified
    to be used for ssh authentication using `ssh -i /path/to/id_rsa`.
* `borg_create_args`: Arguments to pass to the borg create command specifying files and folder to backup and/or exclude.
    See `man borg` for more info.
* `borg_prune_args`: `bsrvd` automatically runs a `borg prune` after each successful backup. This option specifies the
    arguments to supply to this command.
* `schedule`: Schedule defining when to run this backup. The syntax of this value is best explained in the
    [Schedule syntax](#schedule-syntax) section. **TREF** is the previously scheduled event for this job.
* `retry_delay`: Delay in seconds before retrying a failed backup job. Default is `60`.
* `retry_max`: Maximum number of retries before giving up and settling for next scheduled backup time. `0` deactivates
    retrying. Default is `3`.
* `stat_maxage`: When `bsrvstatd` checks this repository, it is satisfied if the last successful backup is not older
    than the given `[TIMEPERIOD]`. This definition is done using `[TIMEPERIOD]` system also used for `@every` in
    relative schedule syntax. It is best explained in the [Schedule syntax](#schedule-syntax) section. If this value is
    not set, `bsrvstatd` will not do checks for this job.

## Schedule syntax

The syntax somewhat loosely follows crontab notation.
In general, there are two ways to specify a schedule:

**1. Relative scheduling**
   
This schedules the next event based on a reference time **TREF**, which is normally the point in time the last event
occurred.

| Alias | Description |
|---|---|
|`@weekly`|Run as soon as **TREF** lies back more than 1 week
|`@daily`|Run as soon as **TREF** lies back more than 1 day
|`@hourly`|Run as soon as **TREF** lies back more than 1 hour
|`@every [TIMEPERIOD]`|Run as soon as **TREF** lies back more than `[TIMEPERIOD]`

`[TIMEPERIOD]` is a string defining a period in time with a list of one or more integers, each followed by one of the
following units:

`week` or `weeks` or `w`,

`day` or `days` or `d`,

`hour` or `hours` or `h`,

`minute` or `minutes` or `m`.

| Example | Description |
|---|---|
| `@every  1minute`| Run as soon as **TREF** lies back more than 1 minute
| `@every 1 week 1 day 1 hour 1 minute` | Run as soon as **TREF** lies back more than 1 week, 1 day, 1 hour, and 1 minute
| `@every 1w1d1h1m` | Same thing
| `@hourly` | Run as soon as **TREF** lies back more than 1 hour
| `@every 2 hours` | Run as soon as **TREF** lies back more than 2 hours

**2. Absolute scheduling**

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
