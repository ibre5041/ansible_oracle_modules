#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_gi_facts
short_description: Returns some facts about Grid Infrastructure environment
description:
  - Returns some facts about Grid Infrastructure environment
  - Must be run on a remote host
version_added: "2.4"
options:
  oracle_home:
    description:
      - Grid Infrastructure home, can be absent if ORACLE_HOME environment variable is set
    required: false
notes:
  - Oracle Grid Infrastructure 12cR1 or later required
  - Must be run as (become) GI owner
author:
  - Ilmar Kerm, ilmar.kerm@gmail.com, @ilmarkerm
  - Ivan Brezina
'''

EXAMPLES = '''
---
- name: Return GI facts
  oracle_gi_facts:
  register: _oracle_gi_facts

- name: GI facts
  debug: var=_oracle_gi_facts
'''

import socket
from subprocess import check_output, CalledProcessError, TimeoutExpired


def exec_program_lines(arguments):
    try:
        output = check_output(arguments, timeout=30)
        return [line.strip().decode() for line in output.splitlines()]
    except CalledProcessError:
        # Just ignore the error
        return ['']
    except TimeoutExpired:
        return ['']


def exec_program(arguments):
    return exec_program_lines(arguments)[0]


def hostname_to_fqdn(hostname):
    if "." not in hostname:
        return socket.getfqdn(hostname)
    else:
        return hostname


class OracleGiFacts:
    def __init__(self, module, ohomes):
        self.module = module
        self.ohomes = ohomes
        self.networks = dict()
        self.vips = dict()
        self.srvctl = os.path.join(ohomes.crs_home, 'bin', 'srvctl')
        self.cemutlo = os.path.join(ohomes.crs_home, 'bin', 'cemutlo')
        self.shorthostname = socket.gethostname().split('.', 1)[0]

    def local_listener(self):
        args = [self.srvctl, 'status', 'listener']
        if self.ohomes.oracle_crs:
            args += ['-n', self.shorthostname]
        listeners_out = exec_program_lines(args)
        re_listener_name = re.compile('Listener (.+) is enabled')
        listeners = []
        out = []
        for line in listeners_out:
            if "is enabled" in line:
                m = re_listener_name.search(line)
                listeners.append(m.group(1))
        for l in listeners:
            config = {}
            output = exec_program_lines([self.srvctl, 'config', 'listener', '-l', l])
            for line in output:
                if line.startswith('Name:'):
                    config['name'] = line[6:]
                elif line.startswith('Type:'):
                    config['type'] = line[6:]
                elif line.startswith('Network:'):
                    config['network'] = line[9:line.find(',')]
                elif line.startswith('End points:'):
                    config['endpoints'] = line[12:]
                    for proto in config['endpoints'].split('/'):
                        p = proto.split(':')
                        config[p[0].lower()] = p[1]
            if "network" in config.keys():
                config['address'] = self.vips[config['network']]['fqdn']
                config['ipv4'] = self.vips[config['network']]['ipv4']
                config['ipv6'] = self.vips[config['network']]['ipv6']
            out.append(config)
        return out

    def scan_listener(self):
        out = dict()
        for n in self.networks.keys():
            output = exec_program_lines([self.srvctl, 'config', 'scan_listener', '-k', n])
            for line in output:
                endpoints = None
                # 19c
                m = re.search('Endpoints: (.+)', line)
                if m is not None:
                    endpoints = m.group(1)
                else:
                    # 18c, 12c
                    m = re.search('SCAN Listener (.+) exists. Port: (.+)', line)
                    if m is not None:
                        endpoints = m.group(2)
                if endpoints:
                    out[n] = dict(network=n
                                  , scan_address=self.scans[n]['fqdn']
                                  , endpoints=endpoints
                                  , ipv4=self.scans[n]['ipv4']
                                  , ipv6=self.scans[n]['ipv6'])
                    for proto in endpoints.split('/'):
                        p = proto.split(':')
                        out[n][p[0].lower()] = p[1]
                    break
        return out

    def get_networks(self):
        out = dict()
        item = dict()
        output = exec_program_lines([self.srvctl, 'config', 'network'])
        for line in output:
            m = re.search('Network ([0-9]+) exists', line)
            if m is not None:
                if "network" in item.keys():
                    out[item['network']] = item
                item = {'network': m.group(1)}
            elif line.startswith('Subnet IPv4:'):
                item['ipv4'] = line[13:]
            elif line.startswith('Subnet IPv6:'):
                item['ipv6'] = line[13:]
        if "network" in item.keys():
            out[item['network']] = item
        return out

    def get_asm(self):
        output = exec_program_lines([self.srvctl, 'config', 'asm'])
        out = dict()
        for line in output:
            try:
                value = line.split(': ')[1]
            except IndexError:
                value = ''
            if line.startswith('ASM home'):
                out.update({'asm_home': value})
            elif line.startswith('Password file'):
                out.update({'pwfile': value})
            elif line.startswith('ASM listener'):
                out.update({'listener': value})
            elif line.startswith('Spfile'):
                out.update({'spfile': value})
            elif line.startswith('ASM diskgroup discovery string'):
                out.update({'diskgroup': value})
        return out

    def get_vips(self):
        output = exec_program_lines([self.srvctl, 'config', 'vip', '-n', self.shorthostname])
        vip = dict()
        out = dict()
        for line in output:
            try:
                value = line.split(': ')[1]
            except IndexError:
                value = ''
            if line.startswith('VIP exists:'):
                if "network" in vip.keys():
                    out[vip['network']] = vip
                vip = {}
                m = re.search('network number ([0-9]+),', line)
                vip['network'] = m.group(1)
            elif line.startswith('VIP Name:'):
                vip['name'] = value
                vip['fqdn'] = hostname_to_fqdn(vip['name'])
            elif line.startswith('VIP IPv4 Address:'):
                vip['ipv4'] = value
            elif line.startswith('VIP IPv6 Address:'):
                vip['ipv6'] = value
        if "network" in vip.keys():
            out[vip['network']] = vip
        return out

    def get_scans(self):
        out = dict()
        item = dict()
        output = exec_program_lines([self.srvctl, 'config', 'scan', '-all'])
        for line in output:
            if line.startswith('SCAN name:'):
                if "network" in item.keys():
                    out[item['network']] = item
                m = re.search('SCAN name: (.+), Network: ([0-9]+)', line)
                item = {'network': m.group(2), 'name': m.group(1), 'ipv4': [], 'ipv6': []}
                item['fqdn'] = hostname_to_fqdn(item['name'])
            else:
                m = re.search('SCAN [0-9]+ (IPv[46]) VIP: (.+)', line)
                if m is not None:
                    item[m.group(1).lower()] += [m.group(2)]
        if "network" in item.keys():
            out[item['network']] = item
        return out


# Ansible code
def main():
    module = AnsibleModule(
        argument_spec=dict(
            oracle_home=dict(required=False, aliases=['oh'])
        ),
        supports_check_mode=True
    )
    # Preparation
    facts = {}
    if module.params["oracle_home"]:
        os.environ['ORACLE_HOME'] = module.params["oracle_home"]

    ohomes = OracleHomes()
    ohomes.list_crs_instances()
    if not ohomes.crsctl:
        ohomes.list_processes()
    if not ohomes.crsctl:
        ohomes.parse_oratab()
    if not ohomes.crs_home:
        module.fail_json(changed=False, msg="Could not find GI home. I can't find executables srvctl or crsctl")

    os.environ['ORACLE_HOME'] = ohomes.crs_home
    oracle_gi_facts = OracleGiFacts(module, ohomes)

    # Cluster name
    facts.update({'clustername': exec_program([oracle_gi_facts.cemutlo, '-n'])})

    # Cluster version
    if ohomes.oracle_crs:
        version = exec_program([ohomes.crsctl, 'query', 'crs', 'activeversion'])
        facts.update({'activeversion': version})
    else:
        for i in ['releaseversion', 'releasepatch', 'softwareversion', 'softwarepatch']:
            version = exec_program([ohomes.crsctl, 'query', 'has', i])
            m = re.search('\[([0-9\.]+)\]$', version)
            if m:
                facts.update({i: m.group(1)})
                facts.update({"version": m.group(1)})  # for backward compatibility
            else:
                facts.update({i: version})

    # ASM
    asm = oracle_gi_facts.get_asm()
    facts.update({'asm': asm})
    # VIPS
    vips = oracle_gi_facts.get_vips()
    facts.update({'vip': list(vips.values())})
    # Networks
    networks = oracle_gi_facts.get_networks()
    facts.update({'network': list(networks.values())})
    # SCANs
    scans = oracle_gi_facts.get_scans()
    facts.update({'scan': list(scans.values())})
    # Listener
    facts.update({'local_listener': oracle_gi_facts.local_listener()})
    facts.update({'scan_listener': list(oracle_gi_facts.scan_listener().values()) if ohomes.oracle_crs else []})
    # Databases
    facts.update({'database_list': exec_program_lines([oracle_gi_facts.srvctl, 'config', 'database'])})
    # ORACLE_CRS_HOME
    facts.update({'oracle_crs_home': os.environ['ORACLE_HOME']})
    # Output
    module.exit_json(msg=" ", changed=False, ansible_facts={"oracle_gi_facts": facts})


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
# try:
#    from ansible.module_utils.oracle_homes import OracleHomes
# except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import *
except:
    pass

if __name__ == '__main__':
    main()
