#!/usr/bin/env python3
from __future__ import print_function
import re
import os
import subprocess
import argparse
from operator import itemgetter

try:
    import psutil
except ImportError:
    psutil = None
# psutil = None

"""
The MIT License (MIT)

Copyright (c) 2015 Mark Gruenberg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__head__ = "$Header: file:///var/svn/db_repo/DBA/trunk/bin/crsstat.py 429 2015-04-28 11:39:50Z mgruen $"
__version__ = "$Revision: 429 $"
__lastchangedate__ = "$Date: 2015-04-28 07:39:50 -0400 (Tue, 28 Apr 2015) $"
__author__ = "$Author: mgruen $"


class NoGridError(Exception):
    def __init__(self, msg):
        msg = msg


def get_gridhome():
    ''' find grid home by looking at the running processes ocssd.bin or
        hasd.bin '''

    grid_home = None
    try:
        paths = [psutil.Process(p).cmdline()[0] for p in psutil.pids()
                 if psutil.Process(p).cmdline() != [] and
                 re.search(r'ocssd.bin|hasd.bin', psutil.Process(p).cmdline()[0])]
    except AttributeError as e:
        out = subprocess.check_output("ps -eo args | grep -E 'ocssd\.bin|hasd\.bin' | grep -v grep", shell=True)
        paths = [e.split()[0].decode('utf-8')  for e in out.splitlines() if len(e.split()) > 0]

    if paths:
        grid_home = os.path.normpath(os.path.join(paths[0], '..', '..'))
    else:
        raise NoGridError("GRID doesn't appear to be running and can't find GRID_HOME")
    return grid_home


def get_has_crs_version(grid_home=None):
    """ CRSCMD="query crs softwareversion"
        HASCMD="query has softwareversion"
        crsctl query crs softwareversion
    """
    if not grid_home:
        grid_home = get_gridhome()
    crs_path = os.path.join(grid_home, 'bin')
    out = subprocess.check_output(os.path.join(crs_path, 'crsctl ') + 'query crs softwareversion', shell=True)
    vers_dict = re.search(r'(?P<host>\[.*\]).*(?P<version>\[[0-9.]+\])', out).groupdict()

    print(out)


def decode_types(rtype):
    """
    :return: decoded resource type
    :rtype : str
    """
    res_types = {
        'ora.listener.type': 'Listener',
        'ora.asm.type': 'ASM',
        'ora.network.type': 'Network',
        'ora.ons.type': 'Ora Notif Serv',
        'ora.scan_listener.type': 'SCAN Listener',
        'ora.mgmtlsnr.type': 'MGMT Listener',
        'ora.database.type': 'Database',
        'ora.cvu.type': 'CVU',
        'ora.mgmtdb.type': 'MGMT Database',
        'ora.oc4j.type': 'oc4j',
        'ora.cluster_vip_net1.type': 'Net1 VIP',
        'ora.scan_vip.type': 'SCAN VIP',
        'ora.service.type': 'Service'
    }
    try:
        dtype = res_types[rtype]
    except KeyError as e:
        dtype = rtype
    return dtype


def crsstat_report(test=False):
    """
    :return: prints formatted resource report
    """
    res = get_resource_attributes(test=test)
    header = ['{:<30} {:<22} {:<7} {:<7} {:<10} {:<28}'.format(
                    'Resource Name',
                    'Type',
                    'Target',
                    'State',
                    'Node',
                    'State Details'),
              '{:-<30} {:-<22} {:-<7} {:-<7} {:-<10} {:-<28}'.format(
                    '', '', '', '', '', '')]

    print('\n'.join(header))
    for rec in res:
        for i, m in enumerate(rec['NODE_STATUS']):
            print('{NAME:<30} {FTYPE:<22}'.format(**rec),  end=' ')
            print('{TARGET: <7} {FSTATE: <7} {NODE:<10} {STATE_DETAILS}'.format(**m))


def get_crs_status(statopt, grid_home=None, test=False):
    """
    get output from crsctl
    :rtype: str
    :return: output from crsctl
    """
    assert statopt in ['basetypes', 'version', 'stats'], \
        "{} isn't valid statopt : ['basetypes', 'version', 'stats']".format(
            statopt)

    if not test:
        if not grid_home:
            grid_home = get_gridhome()
            crs_path = os.path.join(grid_home, 'bin')
        cmd = os.path.join(crs_path, 'crsctl ')
        if statopt == 'basetypes':
            cmd += 'status res -t'
        elif statopt == 'version':
            cmd += 'query crs softwareversion'
        else:
            cmd += 'status res -v'

        try:
            out = subprocess.check_output(cmd, shell=True).decode('utf-8')
        except subprocess.CalledProcessError as e:
            print('Exception occured in crs_status: called {} {!s}'.format(statopt, e))
            raise
    else:
        if statopt == 'stats':
            with open('crs_stats_verbose.txt') as f:
                out = f.read()

    return out


def get_resource_attributes(test=False):
    """
    using crsctl status resource  to get the resource attributes
    :rtype: list of dict
    :return: list of resources sorted by basetype

    """
    res_basetypes = get_resource_basetypes(test=test)
    resources = []
    resource = {}
    metas = []
    meta = {}
    out = get_crs_status('stats', test=test)

    first = True
    for l in out.splitlines():
        if l == '':
            continue
        else:
            e = l.split('=')
            if e[0] == 'NAME':
                if not first:
                    metas.append(meta)
                    resource['NODE_CNT'] = len(metas)
                    resource['NODE_STATUS'] = metas
                    resources.append(resource)
                    resource = {}
                    metas = []
                    meta = {}
                else:
                    first = False
                resource = {'NAME': e[1],
                            'BASETYPE': res_basetypes[e[1]]}
            elif e[0] == 'TYPE':
                resource[e[0]] = e[1]
                resource['FTYPE'] = '{}:{}'.format(
                    decode_types(resource['TYPE']), resource['BASETYPE'])
            else:
                if meta != {} and e[0] == 'LAST_SERVER':
                    metas.append(meta)
                    meta = {}
                    meta[e[0]] = e[1]
                else:
                    meta[e[0]] = e[1]
                    if e[0] == 'STATE':
                        try:
                            meta['NODE'] = e[1].split()[2]
                            meta['FSTATE'] = e[1].split()[0]
                        except IndexError:
                            meta['NODE'] = ''
                            meta['FSTATE'] = e[1].split()[0]
    else:
        metas.append(meta)
        resource['NODE_CNT'] = len(metas)
        resource['NODE_STATUS'] = metas
        resources.append(resource)

    return sorted(resources, key=itemgetter('BASETYPE'), reverse=True)

def get_resource_basetypes(grid_home=None, test=True):
    """
    uses crsctl status resource -t to get the resource and basetype
    :rtype : dict
    """
    if not test:
        if not grid_home:
            grid_home = get_gridhome()
        crs_path = os.path.join(grid_home, 'bin')
        cmd = os.path.join(crs_path, 'crsctl status res -t')
        try:
            out = subprocess.check_output(cmd, shell=True).decode('utf-8')
        except subprocess.CalledProcessError as e:
            print('Exception occured in crs_status: {!s}'.format(e))
    else:
        with open('crs_category.txt', 'r') as f:
            out = f.read().decode('utf-8')
    islocal = False
    iscluster = False
    resource_basetype = {}
    for l in out.splitlines()[3:]:
        m = re.match(r'(?!^Local Resource|^Cluster Resource)^\w', l)
        if m:
            resource_basetype[l] = 'cluster' if iscluster else 'local'
        elif l[:8] == '--------' or l[:3] == '   ':
            continue
        elif l == 'Local Resources':
            islocal = True
            iscluster = False
        elif l == 'Cluster Resources':
            islocal = False
            iscluster = True
        else:
           print("Error unhandled line item {}".format(l))

    return resource_basetype


def main(test=False):
    crsstat_report(test=test)


if __name__ == '__main__':
    test = False
    crsstat_report(test=test)
