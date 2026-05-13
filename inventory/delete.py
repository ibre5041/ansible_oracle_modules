#!/usr/bin/python3

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from utils import *

import atexit
import sys
import logging
import argparse

import dns.update
import dns.query
import dns.tsigkeyring

from config import Config, Machine, VsCreadential

import ssl


def delete_vm(service_instance, machine):
    vm = get_obj(content, [vim.VirtualMachine], machine.nameVSphere)

    if not vm:
        logging.debug("{machine} not found.".format(machine=machine.nameVSphere))
        return

    if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
        task = vm.PowerOff()
        wait_for_tasks(service_instance, [task])
    if vm.runtime.powerState == vim.VirtualMachinePowerState.suspended:
        task = vm.PowerOn()
        wait_for_tasks(service_instance, [task])
        task = vm.PowerOff()
        wait_for_tasks(service_instance, [task])
    task = vm.Destroy_Task()
    wait_for_tasks(service_instance, [task])
    logging.debug("{machine} destroyed.".format(machine=machine.nameVSphere))


def dns_for_vm(machine):
    for arecord in machine.addresses:
        ip = machine.addresses[arecord]
        if isinstance(ip, list):
            delete_dns_record(arecord, 'prod.vmware.haf', None)
        else:
            delete_dns_record(arecord, 'prod.vmware.haf', ip)


# Start program
if __name__ == "__main__":
    ssl._create_default_https_context = ssl._create_unverified_context

    logging.basicConfig(stream=sys.stdout,
                        level=logging.DEBUG,
                        format='%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(message)s')

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-f', '--file',
                       required=False,
                       action='store',
                       help='Config filename to process in .yaml format')

    group.add_argument('-i', '--inventory',
                       required=False,
                       action='store',
                       help='Config filename to process in ansible inventory format')

    args = parser.parse_args()

    # parse yaml file
    if args.file:
        c = Config.createFromYAML(args.file)
    else:
        c = Config.createFromInventory(args.inventory)
    
    # Config
    config = VsCreadential.load('.credentials.yaml')
    # Connect
    si = SmartConnect(
        host=config.hostname,
        user=config.username,
        pwd=config.password,
        port=443)
    # disconnect this thing
    atexit.register(Disconnect, si)

    content = si.RetrieveContent()

    c.validate(content)

    for machine in c.machines:
        delete_vm(service_instance=si, machine=machine)
        dns_for_vm(machine)
    if c.cluster:
        dns_for_vm(c.cluster)

