from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from utils import *

import atexit
import sys
import logging
import argparse
import humanfriendly

from config import Config, VsCreadential

import ssl

logging.basicConfig(stream=sys.stdout,
                    level=logging.DEBUG,
                    format='%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(message)s')

def _create_data_file(service_instance, machine, bus, unit, new_disk_kb):
    logging.debug("Creating data file: {}, {}:{}, {}KB".format(machine.name, bus, unit, new_disk_kb))
    content = service_instance.RetrieveContent()
    path_on_ds = '[{datastore}] {machine}/'.format(datastore=machine.datastore, machine=machine.nameVSphere)
    dc = get_obj(content, [vim.Datacenter], 'Datacenter')
    ds_obj = get_obj(content, [vim.Datastore], machine.datastore)

    fileBackedVirtualDiskSpec = vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
    fileBackedVirtualDiskSpec.capacityKb = int(new_disk_kb)
    # Using vim enums
    fileBackedVirtualDiskSpec.adapterType = vim.VirtualDiskManager.VirtualDiskAdapterType.lsiLogic
    fileBackedVirtualDiskSpec.diskType = vim.VirtualDiskManager.VirtualDiskType.eagerZeroedThick
    logging.debug("Creating VMDK capacityKb: {}; adapterType: {}; diskType: {}"
                  .format(str(fileBackedVirtualDiskSpec.capacityKb)
                          , fileBackedVirtualDiskSpec.adapterType
                          , fileBackedVirtualDiskSpec.diskType))

    path_name = '{path_on_ds}/eager_data_{bus}_{unit}.vmdk'.format(path_on_ds=path_on_ds, bus=str(bus),
                                                                   unit=str(unit))

    virtualDiskManager = content.virtualDiskManager
    new_disk = [virtualDiskManager.CreateVirtualDisk_Task(name=path_name
                                                          , datacenter=dc
                                                          , spec=fileBackedVirtualDiskSpec)]
    logging.debug("VMDK {} creating".format(path_name))
    wait_for_tasks(service_instance, new_disk)
    logging.debug("VMDK {} created successfully".format(path_name))
    uuid = virtualDiskManager.QueryVirtualDiskUuid(name=path_name, datacenter=dc)
    logging.debug("VMDK {} UUID: {}".format(path_name, str(uuid)))

    return path_name


def _add_scsi_adapter(service_instance, vm, machine):
    devices = []
    logging.warn("No SCSI adapter other then busNumber: 0")
    device = None  # 1st SCSI adapter
    for i, scsi_adapter in enumerate(machine.scsiAdapters):
        if i == 0: # skip the 1st SCSI adapter
            continue
        scsi_ctr = vim.vm.device.VirtualDeviceSpec()
        scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
        scsi_ctr.device.deviceInfo = vim.Description()
        scsi_ctr.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
        scsi_ctr.device.slotInfo.pciSlotNumber = scsi_adapter['pciSlotNumber']
        scsi_ctr.device.controllerKey = 100
        scsi_ctr.device.deviceInfo = vim.Description()
        scsi_ctr.device.deviceInfo.label = 'Shared SCSI'
        scsi_ctr.device.deviceInfo.label = 'BUS for Shared SCSI disks'
        scsi_ctr.device.unitNumber = 3
        scsi_ctr.device.busNumber = i
        scsi_ctr.device.hotAddRemove = True
        # 1st SCSI adapter for local disk, rest for shared ones
        scsi_ctr.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing if i == 0 else vim.vm.device.VirtualSCSIController.Sharing.virtualSharing
        scsi_ctr.device.scsiCtlrUnitNumber = 7
        devices.append(scsi_ctr)
        if i != 0:
            logging.warn("Adding SCSI adapter busNumber: {adapter}".format(adapter=i))
            spec = vim.vm.ConfigSpec()
            spec.deviceChange = devices
            task = vm.ReconfigVM_Task(spec=spec)
            wait_for_tasks(service_instance, [task])

            for dev in vm.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualSCSIController):
                    if dev.busNumber == 0:  # Ingnore bus 0, rootdg, appdg
                        continue
                    controller = dev
            logging.debug("Returning newly created adapter: {adapter}".format(adapter=controller))
            return controller


def add_shared_disk(service_instance, config):
    content = service_instance.RetrieveContent()

    first_machine = config.machine(config.cluster.nodes[0])
    vm = get_obj(content, [vim.VirtualMachine], first_machine.nameVSphere)

    # for dev in vm.config.hardware.device:
    #     logging.info(type(dev))
    #     if isinstance(dev, vim.vm.device.VirtualDisk):
    #         print(dev)        

    controller = None
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualSCSIController):
            if dev.busNumber == 0:  # Ingnore bus 0, rootdg, appdg
                continue
            controller = dev
        
    for disk in config.cluster.disks:
        if 'count' in disk:
            count = int(disk['count'])
        else:
            count = 1

        for i in range(0, count):
            spec = vim.vm.ConfigSpec()
            # get all disks on a VM, set unit_number to the next available (start from LUN 15,14,..)
            unit_number = 15
            for dev in vm.config.hardware.device:
                if hasattr(dev.backing, 'fileName') and controller:  # Note assuming this will skip disks on SCSI BUS: 0
                    if dev.controllerKey != controller.key:
                        continue
                    unit_number = int(dev.unitNumber) - 1
                    # unit_number 7 reserved for scsi controller
                    if unit_number == 7:
                        unit_number -= 1
                    if unit_number >= 16:
                        logging.error("we don't support this many disks")
                        return
                    if unit_number < 3 :
                        logging.error("LUNs 0-2 are reserved for OS")
                        return

            new_disk_kb = int(humanfriendly.parse_size(str(disk['size']), binary=True) / 1024 )
            path_name = _create_data_file(service_instance, first_machine, 1, unit_number, new_disk_kb)

            for node in config.cluster.nodes:
                machine = config.machine(node)
                vm = get_obj(content, [vim.VirtualMachine], machine.nameVSphere)
                for dev in vm.config.hardware.device:
                    if isinstance(dev, vim.vm.device.VirtualSCSIController):
                        if dev.busNumber == 0:  # Ingnore bus 0, rootdg, appdg
                            continue
                        controller = dev

                if controller == None:
                    controller = _add_scsi_adapter(service_instance, vm, machine)
                            
                # add disk here
                dev_changes = []
                disk_spec = vim.vm.device.VirtualDeviceSpec()
                disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                # device config
                disk_spec.device = vim.vm.device.VirtualDisk()
                disk_spec.device.unitNumber = unit_number
                # disk_spec.device.capacityInKB = size
                disk_spec.device.controllerKey = controller.key
                # device backing info
                disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
                disk_spec.device.backing.thinProvisioned = False
                disk_spec.device.backing.diskMode = vim.vm.device.VirtualDiskOption.DiskMode.persistent
                disk_spec.device.backing.fileName = path_name
                disk_spec.device.backing.writeThrough = True

                disk_spec.device.backing.sharing = 'sharingMultiWriter'

                dev_changes.append(disk_spec)
                spec.deviceChange = dev_changes
                task = vm.ReconfigVM_Task(spec=spec)
                wait_for_tasks(service_instance, [task])
                logging.debug("{machine} Added disk {size}GB {path}".format(machine=machine.nameVSphere, size=disk['size'], path=path_name))



def add_data_disk(service_instance, machine, disk):
    content = service_instance.RetrieveContent()
    vm = get_obj(content, [vim.VirtualMachine], machine.nameVSphere)

    controller = None
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualSCSIController):
            if dev.busNumber == 0: # Ingnore bus 0, rootdg, appdg
                continue
            logging.debug('Found controller: ({}) {}'.format(dev.key, dev))
            controller = dev

    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualDisk):
            logging.debug('Found disk: {} => {}'.format(dev.key, dev.controllerKey))
            if dev.controllerKey == controller.key:
                print(dev)

    if 'count' in disk:
        count = int(disk['count'])
    else:
        count = 1

    for i in range(0, count):
        spec = vim.vm.ConfigSpec()
        # get all disks on a VM, set unit_number to the next available
        unit_number = 0
        for dev in vm.config.hardware.device:
            if hasattr(dev.backing, 'fileName') and controller:  # Note assuming this will skip disks on SCSI BUS: 0
                if dev.controllerKey != controller.key:
                    continue
                unit_number = int(dev.unitNumber) + 1
                # unit_number 7 reserved for scsi controller
                if unit_number == 7:
                    unit_number += 1
                if unit_number >= 16:
                    logging.debug("we don't support this many disks")

        new_disk_kb = int(humanfriendly.parse_size(disk['size'], binary=True) / 1024 )
        path_name = _create_data_file(service_instance, machine, 1, unit_number, new_disk_kb)

        # add disk here
        dev_changes = []
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        # device config
        disk_spec.device = vim.vm.device.VirtualDisk()
        disk_spec.device.unitNumber = unit_number
        # disk_spec.device.capacityInKB = size
        disk_spec.device.controllerKey = controller.key
        # device backing info
        disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        disk_spec.device.backing.thinProvisioned = False
        disk_spec.device.backing.diskMode = vim.vm.device.VirtualDiskOption.DiskMode.persistent
        disk_spec.device.backing.fileName = path_name
        disk_spec.device.backing.writeThrough = True

        disk_spec.device.backing.sharing = 'sharingMultiWriter'

        dev_changes.append(disk_spec)
        spec.deviceChange = dev_changes
        task = vm.ReconfigVM_Task(spec=spec)
        wait_for_tasks(service_instance, [task])
        logging.debug("{machine} Added disk {size}GB {path}".format(machine=machine.nameVSphere, size=disk['size'], path=path_name))

# Start program
if __name__ == "__main__":
    ssl._create_default_https_context = ssl._create_unverified_context

    logging.basicConfig(stream=sys.stdout,
                        level=logging.DEBUG,
                        format='%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(message)s')

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

    for machine in c.machines:
        for disk in machine.disks:
            if disk['bus'] == 0:
                continue
            add_data_disk(service_instance=si, machine=machine, disk=disk)

    if c.cluster:
        add_shared_disk(service_instance=si, config=c)

