#!/usr/bin/python3

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from utils import *

import atexit
import sys
import logging
import socket
import humanfriendly
import argparse

from config import Config, Machine, VsCreadential

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(stream=sys.stdout,
                    level=logging.DEBUG,
                    format='%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(message)s')


def create_vm(service_instance, machine):
    devices = []
    datastore_path = machine.pathVSphere
    vmx_file = vim.vm.FileInfo(logDirectory=None
                               , snapshotDirectory=None
                               , suspendDirectory=None
                               , vmPathName=datastore_path)

    for net_adapter in machine.netAdapters:
        net = get_obj(content, [vim.Network], net_adapter['network'])
        nicspec = vim.vm.device.VirtualDeviceSpec()
        nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        nic_type = vim.vm.device.VirtualVmxnet3()
        nicspec.device = nic_type
        # https://kb.vmware.com/s/article/2047927
        nicspec.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
        nicspec.device.slotInfo.pciSlotNumber = net_adapter['pciSlotNumber']
        if machine.name != 'rhel7-template': # a machine build as teamplate should not have manualy generated MAC addresses
            if 'mac' in net_adapter:
                nicspec.device.addressType = 'manual'
                nicspec.device.macAddress = net_adapter['mac']
        nicspec.device.deviceInfo = vim.Description()
        nicspec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        nicspec.device.backing.network = net
        nicspec.device.backing.deviceName = net.name
        nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nicspec.device.connectable.startConnected = True
        nicspec.device.connectable.allowGuestControl = True
        devices.append(nicspec)

    device = None  # 1st SCSI adapter
    for i, scsi_adapter in enumerate(machine.scsiAdapters):
        scsi_ctr = vim.vm.device.VirtualDeviceSpec()
        scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
        scsi_ctr.device.deviceInfo = vim.Description()
        scsi_ctr.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
        scsi_ctr.device.slotInfo.pciSlotNumber = scsi_adapter['pciSlotNumber']
        scsi_ctr.device.controllerKey = 100
        scsi_ctr.device.deviceInfo = vim.Description()
        #scsi_ctr.device.deviceInfo.label = 'Shared SCSI'
        scsi_ctr.device.deviceInfo.label = 'BUS for Local SCSI disks'
        scsi_ctr.device.unitNumber = 3
        scsi_ctr.device.busNumber = i
        scsi_ctr.device.hotAddRemove = True
        # 1st SCSI adapter for local disk, rest for shared ones
        scsi_ctr.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing if i == 0 else vim.vm.device.VirtualSCSIController.Sharing.virtualSharing
        scsi_ctr.device.scsiCtlrUnitNumber = 7
        devices.append(scsi_ctr)
        if i == 0:
            device = scsi_ctr.device

    # for i, disk in enumerate(machine.disks):
    #     sizeB = humanfriendly.parse_size(disk['size'], binary=True)
    #     controller = device
    #     disk_spec = vim.vm.device.VirtualDeviceSpec()
    #     disk_spec.fileOperation = "create"
    #     disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    #     disk_spec.device = vim.vm.device.VirtualDisk()
    #     disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    #     disk_spec.device.backing.eagerlyScrub = False
    #     disk_spec.device.backing.thinProvisioned = True
    #     #disk_spec.device.backing.thinProvisioned = False
    #     disk_spec.device.backing.diskMode = 'persistent'
    #     disk_spec.device.backing.fileName = disk['pathVSphere']
    #     disk_spec.device.unitNumber = i
    #     disk_spec.device.capacityInKB = int(sizeB / 1024)
    #     disk_spec.device.controllerKey = controller.key
    #     devices.append(disk_spec)

    # dc = get_obj(content, [vim.Datacenter], 'Datacenter')
    # allhosts = []
    # for entity in dc.hostFolder.childEntity:
    #     for host in entity.host:
    #         allhosts.append(host)
    # print(allhosts)
    # dc_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.Datacenter], True)

    rp = service_instance.RetrieveContent().rootFolder.childEntity[0].hostFolder.childEntity[0].resourcePool
    vm_folder = get_obj(content, [vim.Folder], machine.folder)
    config = vim.vm.ConfigSpec(name=machine.nameVSphere
                               , memoryMB=6 * 1024  # TODO
                               , numCPUs=machine.cpu
                               , files=vmx_file
                               , guestId='centos7_64Guest'
                               , version='vmx-13'
                               , deviceChange=devices)

    config.extraConfig = []

    opt = vim.option.OptionValue()
    opt.key = 'guestinfo.hostname'
    opt.value = machine.name
    config.extraConfig.append(opt)

    opt = vim.option.OptionValue()
    opt.key = 'guestinfo.dns'
    opt.value = '192.168.8.200'
    config.extraConfig.append(opt)

    if machine.name != 'rhel7-template': # a machine build as teamplate should not have guestinfo IP records
        prod_ip = socket.gethostbyname("{host}.prod.vmware.haf".format(host=machine.name))
        opt = vim.option.OptionValue()
        opt.key = 'guestinfo.prod_ip'
        opt.value = prod_ip
        config.extraConfig.append(opt)

        try:
            barn_ip = socket.gethostbyname("{host}.barn.vmware.haf".format(host=machine.name))
            opt = vim.option.OptionValue()
            opt.key = 'guestinfo.barn_ip'
            opt.value = barn_ip
            config.extraConfig.append(opt)
        except:
            logging.warn("No IP for: {host}.barn.vmware.haf in DNS".format(host=machine.name))

    task = vm_folder.CreateVM_Task(config=config
                                   #, host=esx_host
                                   , pool=rp
                                   )
    vm = wait_for_tasks(service_instance, [task])
    logging.debug("{machine} created.".format(machine=machine.nameVSphere))

    controller = None
    vm = get_obj(content, [vim.VirtualMachine], machine.nameVSphere)
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.ParaVirtualSCSIController):
            if dev.busNumber == 0:
                controller = dev

    for i, disk in enumerate(machine.disks):
        devices = []
        sizeB = humanfriendly.parse_size(disk['size'], binary=True)
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.fileOperation = "create"
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        disk_spec.device = vim.vm.device.VirtualDisk()
        disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        disk_spec.device.backing.eagerlyScrub = False
        disk_spec.device.backing.thinProvisioned = True
        #disk_spec.device.backing.thinProvisioned = False
        disk_spec.device.backing.diskMode = 'persistent'
        disk_spec.device.backing.fileName = disk['pathVSphere']
        disk_spec.device.unitNumber = i
        disk_spec.device.capacityInKB = int(sizeB / 1024)
        #disk_spec.device.controllerKey = controller.key
        disk_spec.device.controllerKey = 1000
        devices.append(disk_spec)

        spec = vim.vm.ConfigSpec()
        spec.deviceChange = devices
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_tasks(service_instance, [task])
        logging.debug("{machine} disk added({i})".format(machine=machine.nameVSphere, i=i))

    vm = get_obj(content, [vim.VirtualMachine], machine.nameVSphere)
    task = vm.PowerOn()
    wait_for_tasks(service_instance, [task])
    logging.debug("{machine} state: {state}".format(machine=machine.nameVSphere, state=str(vm.runtime.powerState)))


def dns_for_vm(machine):
    keyring = dns.tsigkeyring.from_text({
        "dynamic.vmware.haf.": "jn694IwJ9IP4i5yGtSdIZJTFeFpVEvK2wa78gHVX8PohLNBQVYQd+JyGNX8A3hju8WmsNVo1Oq58YS93HR4HIQ=="
    })

    for arecord in machine.addresses:        
        logging.debug("DNS Record: {} ({})".format(arecord, machine.addresses[arecord]))        
        ip = machine.addresses[arecord]
        if isinstance(ip, list):
            for i in ip:
                add_dns_record(arecord, 'prod.vmware.haf', i)
        else:
            create_dns_record(arecord, 'prod.vmware.haf', ip)
            byte = ip.split('.')[-1]
            barn_ip = '10.0.0.' + byte
            create_dns_record(arecord, 'barn.vmware.haf', barn_ip)


# Start program
if __name__ == "__main__":
    # parse yaml file
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file',
                        required=False,
                        action='store',
                        help='Config filename to process', default='rhel7-a.yaml')

    args = parser.parse_args()
    #
    c = Config.createFromYAML(args.file)
    # Connect
    config = VsCreadential.load('.credentials.yaml')
    #
    si = SmartConnect(
        host=config.hostname,
        user=config.username,
        pwd=config.password,
        port=443)
    # disconnect this thing
    atexit.register(Disconnect, si)

    content = si.RetrieveContent()

    c.validate(content)

    #sys.exit(0)

    for machine in c.machines:
        dns_for_vm(machine)
        create_vm(service_instance=si, machine=machine)

    #for disk in c.cl

