#!/usr/bin/env python3

import logging
import multiprocessing
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from pwd import getpwnam
from pwd import getpwuid


ORATAB_LOCATION = '/etc/oratab'
JOURNAL_SOCKET = '/run/systemd/journal/socket'
SERVICE_USER = os.environ.get('ORACLE_DATABASE_USER', 'oracle')
CGROUP_CHECK_INTERVAL = int(os.environ.get('CGROUP_CHECK_INTERVAL', 120))


manager = multiprocessing.Manager()
oracle_ns = manager.Namespace()
oracle_ns.running = True
oracle_ns.oracle_sid = None
oracle_ns.oratab_item = None


class JournalHandler(logging.Handler):
    priority_map = {
        logging.DEBUG: 7,
        logging.INFO: 6,
        logging.WARNING: 4,
        logging.ERROR: 3,
        logging.CRITICAL: 2,
    }

    def __init__(self, identifier):
        super().__init__()
        self.identifier = identifier
        self.exception_formatter = logging.Formatter()

    def emit(self, record):
        try:
            message = record.getMessage()
            if record.exc_info:
                message = '{}\n{}'.format(message, self.exception_formatter.formatException(record.exc_info))

            fields = {
                'MESSAGE': message,
                'PRIORITY': str(self.priority_map.get(record.levelno, 5)),
                'SYSLOG_IDENTIFIER': self.identifier,
                'LOGGER': record.name,
                'CODE_FILE': record.pathname,
                'CODE_LINE': str(record.lineno),
                'CODE_FUNC': record.funcName,
            }
            payload = bytearray()
            for key, value in fields.items():
                payload.extend(self._journal_field(key, value))

            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.connect(JOURNAL_SOCKET)
                sock.sendall(payload)
        except OSError:
            sys.stderr.write('{}: {}\n'.format(record.levelname, record.getMessage()))
        except Exception:
            self.handleError(record)

    @staticmethod
    def _journal_field(key, value):
        key_bytes = key.encode('ascii')
        value_bytes = str(value).encode('utf-8', errors='replace')
        if b'\n' not in value_bytes:
            return key_bytes + b'=' + value_bytes + b'\n'
        return key_bytes + b'\n' + struct.pack('<Q', len(value_bytes)) + value_bytes + b'\n'


log = logging.getLogger(__name__)
log.addHandler(JournalHandler(os.path.basename(__file__)))
log.setLevel(logging.INFO)


def notify(state):
    notify_socket = os.environ.get('NOTIFY_SOCKET')
    if not notify_socket:
        return False

    if notify_socket[0] == '@':
        notify_socket = '\0' + notify_socket[1:]

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(notify_socket)
            sock.sendall(state.encode('utf-8'))
        return True
    except OSError as err:
        log.debug('Unable to notify systemd: %s', err)
        return False


def child_process_env(base_env=None):
    child_env = (base_env or os.environ).copy()
    child_env.pop('NOTIFY_SOCKET', None)
    return child_env


def setugid(user):
    try:
        passwd = getpwuid(int(user))
    except ValueError:
        passwd = getpwnam(user)

    uid = os.getuid()
    if uid != 0:
        log.warning('Not running as root. Cannot drop permissions.')
    elif passwd.pw_uid == uid:
        log.debug('Already running as user %s', passwd.pw_name)
    else:
        log.debug('Switching to user %s', passwd.pw_name)
        os.initgroups(passwd.pw_name, passwd.pw_gid)
        os.setgid(passwd.pw_gid)
        os.setuid(passwd.pw_uid)
        os.environ['HOME'] = passwd.pw_dir


def parse_oratab_sid(oracle_sid):
    log.info('Parsing oratab: %s', ORATAB_LOCATION)
    with open(ORATAB_LOCATION, mode='r', encoding='utf-8') as oratab_fh:
        for line in oratab_fh:
            line = line.split('#', 1)[0].strip()
            if not line:
                continue

            parts = line.split(':')
            if len(parts) < 3:
                continue

            if parts[0] == oracle_sid:
                return {
                    'oracle_home': parts[1],
                    'oracle_flag': parts[2],
                }

    raise KeyError('Oracle SID not found in {}: {}'.format(ORATAB_LOCATION, oracle_sid))


def run_sqlplus(query, oracle_sid, oratab_item):
    oracle_home = oratab_item['oracle_home']
    sqlplus_env = child_process_env()
    sqlplus_env['PATH'] = sqlplus_env['PATH'] + ':{}/bin'.format(oracle_home)
    sqlplus_env['ORACLE_SID'] = oracle_sid
    sqlplus_env['ORACLE_HOME'] = oracle_home

    try:
        sqlplus_env['ORACLE_BASE'] = subprocess.check_output(
            ['{}/bin/orabase'.format(oracle_home)], env=sqlplus_env).decode('utf-8').strip()
    except subprocess.CalledProcessError as err:
        log.warning('Cannot determine ORACLE_BASE by using %s', err.cmd)
        log.debug('Error: %s', repr(err.output))

    log.debug('ORACLE_SID: %s', sqlplus_env['ORACLE_SID'])
    log.debug('ORACLE_HOME: %s', sqlplus_env['ORACLE_HOME'])
    if sqlplus_env.get('ORACLE_BASE') is not None:
        log.debug('ORACLE_BASE: %s', sqlplus_env['ORACLE_BASE'])

    with subprocess.Popen(['sqlplus', '-S', '/nolog'],
                          env=sqlplus_env,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as sqlplus:
        stdout, stderr = sqlplus.communicate(query.encode('utf-8'))
        for line in stdout.decode('utf-8', errors='replace').splitlines():
            log.debug('SQLPLUS> %s', repr(line))
        for line in stderr.decode('utf-8', errors='replace').splitlines():
            log.warning('SQLPLUS stderr> %s', repr(line))
        if sqlplus.returncode != 0:
            raise subprocess.CalledProcessError(sqlplus.returncode, sqlplus.args, stdout, stderr)


def start_db(oracle_sid, oratab_item):
    setugid(SERVICE_USER)
    oracle_flag = oratab_item['oracle_flag']
    if oracle_flag not in ('Y', 'S'):
        log.info('Skipping database %s', oracle_sid)
        return

    startup_mode = 'startup'
    if oracle_flag == 'S':
        startup_mode = 'startup mount'

    log.info('Starting database %s', oracle_sid)
    startup_sql = '''
set head off feedback off
set pages 0 lines 300 trimspool on trimout on
connect / as sysdba
{}
exit
'''
    run_sqlplus(startup_sql.format(startup_mode), oracle_sid, oratab_item)


def stop_db(oracle_sid, oratab_item):
    setugid(SERVICE_USER)
    oracle_flag = oratab_item['oracle_flag']
    if oracle_flag not in ('Y', 'S'):
        log.info('Skipping database %s', oracle_sid)
        return

    log.info('Stopping database %s', oracle_sid)
    shutdown_sql = '''
set head off feedback off
set pages 0 lines 300 trimspool on trimout on
connect / as sysdba
shutdown immediate
exit
'''
    run_sqlplus(shutdown_sql, oracle_sid, oratab_item)


def discover_database_pids(oracle_sid, oracle_home):
    pids = []
    oracle_binary = os.path.realpath(os.path.join(oracle_home, 'bin', 'oracle'))
    sid_suffix = '_{}'.format(oracle_sid)

    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue

        proc_dir = os.path.join('/proc', pid)
        try:
            exe_path = os.path.realpath(os.readlink(os.path.join(proc_dir, 'exe')))
            if exe_path != oracle_binary:
                continue

            names = []
            with open(os.path.join(proc_dir, 'comm'), mode='r', encoding='utf-8') as comm_fh:
                names.append(comm_fh.read().strip())
            with open(os.path.join(proc_dir, 'cmdline'), mode='rb') as cmdline_fh:
                cmdline = cmdline_fh.read().replace(b'\0', b' ').decode('utf-8', errors='replace').strip()
                if cmdline:
                    names.append(os.path.basename(cmdline.split()[0]))

            if any(name.startswith('ora_') and name.endswith(sid_suffix) for name in names):
                pids.append(pid)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue

    return sorted(set(pids), key=int)


def attach_pids_to_systemd_unit(pids):
    pids = get_pids_outside_own_cgroup(pids)
    if not pids:
        return

    unit_name = os.environ.get('ORACLE_SYSTEMD_UNIT', 'oracle-db@{}.service'.format(oracle_ns.oracle_sid))
    log.debug('Attaching processes to %s: %s', unit_name, repr(pids))
    command = [
        'busctl',
        'call',
        'org.freedesktop.systemd1',
        '/org/freedesktop/systemd1',
        'org.freedesktop.systemd1.Manager',
        'AttachProcessesToUnit',
        'ssau',
        unit_name,
        '',
        str(len(pids)),
    ] + pids

    try:
        result = subprocess.run(command,
                                env=child_process_env(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True)
        if result.stdout:
            log.debug('busctl stdout: %s', result.stdout.decode('utf-8', errors='replace').strip())
    except subprocess.CalledProcessError as err:
        stdout = err.stdout.decode('utf-8', errors='replace').strip() if err.stdout else ''
        stderr = err.stderr.decode('utf-8', errors='replace').strip() if err.stderr else ''
        if stdout:
            log.warning('busctl stdout: %s', stdout)
        if stderr:
            log.warning('busctl stderr: %s', stderr)
        log.warning('Failed to attach processes with systemd D-Bus: %s', err)
    except FileNotFoundError as err:
        log.warning('Failed to attach processes with systemd D-Bus: %s', err)


def get_pids_outside_own_cgroup(pids):
    try:
        own_cgroup_path = get_process_cgroup_path(os.getpid())
    except OSError as err:
        log.warning('Cannot determine own cgroup, attaching all discovered processes: %s', err)
        return pids

    missing_pids = []
    for pid in pids:
        try:
            pid_cgroup_path = get_process_cgroup_path(pid)
        except FileNotFoundError:
            continue
        except OSError as err:
            log.warning('Cannot determine cgroup for PID %s, including it in attach list: %s', pid, err)
            missing_pids.append(pid)
            continue

        if pid_cgroup_path != own_cgroup_path and not pid_cgroup_path.startswith(own_cgroup_path + '/'):
            missing_pids.append(pid)

    return missing_pids


def get_process_cgroup_path(pid):
    with open('/proc/{}/cgroup'.format(pid), mode='r', encoding='utf-8') as proc_fh:
        cgroup_path = None
        for line in proc_fh:
            parts = line.strip().split(':', 2)
            if len(parts) != 3:
                continue
            if parts[0] == '0':
                return parts[2]
            if parts[1] == 'name=systemd':
                cgroup_path = parts[2]

    if cgroup_path is None:
        raise FileNotFoundError('systemd cgroup entry not found for PID {}'.format(pid))
    return cgroup_path


def cgroups_checks():
    log.info('Running cgroups_checks for database %s...', oracle_ns.oracle_sid)
    while oracle_ns.running:
        pids = discover_database_pids(oracle_ns.oracle_sid, oracle_ns.oratab_item['oracle_home'])
        attach_pids_to_systemd_unit(pids)
        time.sleep(CGROUP_CHECK_INTERVAL)
    log.info('cgroups_checks stopped for database %s', oracle_ns.oracle_sid)


def handler_stop_signals(_signum, _frame):
    log.info('Received TERM-signal')
    oracle_ns.running = False


def handler_stop_oracle(_signum, _frame):
    log.info('Received STOP-signal')
    stopproc = multiprocessing.Process(target=stop_db,
                                       args=(oracle_ns.oracle_sid, oracle_ns.oratab_item),
                                       name='stop-db-{}'.format(oracle_ns.oracle_sid))
    stopproc.start()
    stopproc.join()
    if stopproc.exitcode != 0:
        log.error('Database stop process failed for %s with exit code %s',
                  oracle_ns.oracle_sid, stopproc.exitcode)
    oracle_ns.running = False


def handler_reloadoratab(_signum, _frame):
    log.info('Received SIGHUP-signal')
    oracle_ns.oratab_item = parse_oratab_sid(oracle_ns.oracle_sid)


def main():
    signal.signal(signal.SIGTERM, handler_stop_signals)
    signal.signal(signal.SIGUSR2, handler_stop_oracle)
    signal.signal(signal.SIGHUP, handler_reloadoratab)

    if len(sys.argv) > 1:
        oracle_sid = sys.argv[1]
    else:
        oracle_sid = os.environ.get('ORACLE_SID')

    if not oracle_sid:
        log.error('Oracle SID must be supplied as argv[1] or ORACLE_SID')
        notify('ERRNO=1')
        return 1

    oracle_ns.oracle_sid = oracle_sid
    try:
        oracle_ns.oratab_item = parse_oratab_sid(oracle_sid)
    except (OSError, KeyError) as err:
        log.error('%s', err)
        notify('ERRNO=1')
        return 1

    notify('STATUS=Starting database {}'.format(oracle_sid))
    startproc = multiprocessing.Process(target=start_db,
                                        args=(oracle_sid, oracle_ns.oratab_item),
                                        name='start-db-{}'.format(oracle_sid))
    startproc.start()
    startproc.join()
    if startproc.exitcode != 0:
        log.error('Database start process failed for %s with exit code %s', oracle_sid, startproc.exitcode)
        notify('ERRNO=1')
        return startproc.exitcode

    attach_pids_to_systemd_unit(discover_database_pids(oracle_sid, oracle_ns.oratab_item['oracle_home']))

    cgchecks = multiprocessing.Process(target=cgroups_checks, name='cgroups-checker-{}'.format(oracle_sid))
    cgchecks.start()

    notify('READY=1\nSTATUS=Started database {}'.format(oracle_sid))
    log.info('Started database %s', oracle_sid)

    while oracle_ns.running:
        time.sleep(CGROUP_CHECK_INTERVAL)

    cgchecks.terminate()
    cgchecks.join()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
