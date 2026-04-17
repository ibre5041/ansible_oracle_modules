import yaml
import json
import logging
import sys
import copy
import socket
import utils

from pyVmomi import vim

from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager


class VsCreadential:
    def __init__(self):
        self.username = None
        self.password = None
        self.hostname = None
        self.validateSSL = False

    @classmethod
    def load(cls, configfile='.credentials.yaml'):
        retval = cls()
        with open(configfile, 'r') as stream:
            content = yaml.safe_load(stream)

            if content and content.keys():
                config = content.keys()
                for key in content.keys():
                    c = content[key]
                    if "username" in c:
                        retval.username = str(c['username'])

                    if "password" in c:
                        retval.password = str(c['password'])

                    if "hostname" in c:
                        retval.hostname = str(c['hostname'])

                    if "validateSSL" in c:
                        retval.ssl = c['validateSSL']
            content['config']['password'] = '****'
            logging.debug(json.dumps(content, indent=4, sort_keys=True))
        return retval


class Cluster:
    def __init__(self):
        self.disks = []  # assume all disks are local, attached to 1st scsi adapter
        self.datastore = 'Datastore'
        self.nodes = []
        self.addresses = dict()

    @classmethod
    def createFromDict(cls, dictionary):
        retval = cls()
        if 'disks' in dictionary:
            for disk in dictionary['disks']:
                # It looks like yaml parser and ansible yaml parser produce different
                # Data structures for the same input
                if disk['disk']:
                    retval.disks.append(disk['disk'])
                else:
                    retval.disks.append(disk)

        if 'nodes' in dictionary:
            for node in dictionary['nodes']:
                retval.nodes.append(str(node))

        if 'addresses' in dictionary and dictionary['addresses'] and isinstance(dictionary['addresses'], dict):
            a = dictionary['addresses']
            for name in a:
                retval.addresses[name] = a[name]

        if retval.nodes:
            logging.debug('Cluster nodes: {nodes}'.format(nodes=str(retval.nodes)))
        return retval


class Machine:
    def __init__(self, name):
        self.name = name
        self.ram = 1024 # 1024MB = 1GB RAM
        self.cpu = 1    # 1 vCPU Core
        self.scsiAdapters = []
        self.netAdapters = []
        self.disks = []  # assume all disks are local, attached to 1st scsi adapter
        self.datastore = 'Datastore'
        self.folder = 'Datacenter'
        self.template = 'RHEL7 Template'
        self.addresses = dict()

    @classmethod
    def createFromDict(cls, dictionary, name=None):
        retval = cls(name)
        Machine._dictUpdate(retval, dictionary)
        if name:
            retval.name = name
        # do not call _sanitize here, default Machine does not need it
        return retval

    def updateFromDict(self, dictionary, name=None):
        # clone self 1st
        retval = copy.deepcopy(self)
        Machine._dictUpdate(retval, dictionary)
        retval._sanitize()
        return retval

    @staticmethod
    def _dictUpdate(instance, dictionary):
        if "name" in dictionary:
            instance.name = dictionary['name']
        if "template" in dictionary:
            instance.template = dictionary['template']
        if "ram" in dictionary:
            instance.ram = dictionary['ram']
        if "cpu" in dictionary:
            instance.cpu = dictionary['cpu']
        if "scsi" in dictionary:
            for s in dictionary['scsi']:
                instance.scsiAdapters.append(s['adapter'])

        if "disks" in dictionary:
            for d in dictionary['disks']:
                # It looks like yaml parser and ansible yaml parser produce different
                # Data structures for the same input
                #if d['disk']:
                #    instance.disks.append(d['disk'])
                #else:
                instance.disks.append(d)
        if "vmware" in dictionary:
            if "vm_folder" in dictionary['vmware']:
                instance.folder = dictionary['vmware']['vm_folder']
            if "datastore" in dictionary['vmware']:
                instance.datastore = dictionary['vmware']['datastore']
        if "network" in dictionary and dictionary['network']:
            for adapter in dictionary['network']:
                # It looks like yaml parser and ansible yaml parser produce different
                # Data structures for the same input
                if adapter['adapter']:
                    instance.netAdapters.append(adapter['adapter'])
                else:
                    instance.netAdapters.append(adapter)

        if "addresses" in dictionary and dictionary['addresses'] and isinstance(dictionary['addresses'], dict):
            a = dictionary['addresses']
            for name in a:
                instance.addresses[name] = a[name]


    def _sanitize(self):
        self.ramVSphere = self.ram
        self.nameVSphere = self.name
        #
        for i, disk in enumerate(self.disks):
            disk['sizeVSphere'] = disk['size']
            if disk['disk']:
                filename = '{vm}_{dg}.vdmk'.format(vm=self.name.replace('-','_'), dg=disk['disk'])
            else:
                filename = '{vm}_{dg}.vdmk'.format(vm=self.name.replace('-','_'), dg=i)
            disk['pathVSphere'] = '[{datastore}] {vmname}/{filename}'\
                .format(datastore=self.datastore
                        , vmname=self.nameVSphere
                        , filename=filename
                        )
            if 'scsiUnit' not in disk:
                disk['scsiUnit'] = ( i if i < 7 else i+1)  # exclude num 7, reserved for SCSI Adapter
        self.pathVSphere = '[{datastore}] {vmname}/'.format(datastore=self.datastore, vmname=self.nameVSphere)
        #
        try:
            ip = socket.gethostbyname(self.name)
        except:
            if self.name not in self.addresses:
                logging.error("Cloud not deduce IP for: {}".format(self.name))
            ip = self.addresses[self.name]
        if ip:
            # machine id is the last byte of IP
            vmwareMACBase = "00:50:56:{:02d}:{:02d}:{:02d}"
            machineId = ip.split('.')[-1]
            (machineIdA, machineIdB) = divmod(int(machineId), 100)
            for i, net in enumerate(self.netAdapters):
                net['mac'] = vmwareMACBase.format(int(i), int(machineIdA), int(machineIdB))
                logging.debug("{host} Net adapter {order} IP:{ip} MAC:[{mac}]"
                              .format(host=self.name
                                      , order=i
                                      , ip=ip
                                      , mac=net['mac']))



    def validate(self, content):
        ds = utils.get_obj(content, [vim.Datastore], self.datastore)
        logging.debug('{} Datastore: {:<12} {}'.format(self.name, str(self.datastore), bool(ds)))

        vf = utils.get_obj(content, [vim.Folder], self.folder)
        logging.debug('{} VM Folder: {:<12} {}'.format(self.name, str(self.folder), bool(vf)))

        for disk in self.disks:
            logging.debug('{}  VM Disk: {:<12} {}'.format(self.name, str(disk['disk']), bool(disk['bus'] == 0)))

        for adapter in self.netAdapters:
            net = utils.get_obj(content, [vim.Network], adapter['network'])
            logging.debug('{}  Net Adapter: {:<12} {}'.format(self.name, str(adapter['network']), bool(net)))


class Config:

    def __init__(self):
        self.name = "Config"
        self.machines = []
        self.cluster = None

    def machine(self, name):
        for m in self.machines:
            if name == m.name:
                return m
        return None

    @classmethod
    def createFromYAML(cls, yaml_file):
        retval = cls()
        default = None
        with open(yaml_file, 'r') as stream:
            try:
                content = yaml.safe_load(stream)
                logging.debug("Loaded config: {}".format(str(yaml_file)))
                logging.debug(json.dumps(content, indent=4, sort_keys=True))

                if 'default' in content:
                    defaultMachine = Machine.createFromDict(content['default'], 'default')
                    logging.debug('Default machine loaded: {}'.format(defaultMachine.name))
                for i in content:
                    if 'default' in i:
                        defaultMachine = Machine.createFromDict(i, 'default')
                        logging.debug('Default machine loaded: {}'.format(defaultMachine.name))

                for i in content:
                    if 'machine' in i:
                        if defaultMachine:
                            machine = defaultMachine.updateFromDict(i)
                        else:
                            machine = Machine.createFromDict(i, i['name'])
                        retval.machines.append(machine)
                        logging.debug('Machine loaded: {:<20} CPU: {:<2} RAM: {:<4} Storage: {}'
                                      .format(machine.name
                                              , machine.cpu
                                              , machine.ram
                                              , str(machine.disks)
                                              )
                                      )
                    if 'cluster' in i:
                        cluster = Cluster.createFromDict(i)
                        retval.cluster = cluster

            except yaml.YAMLError as exc:
                print(exc)
        return retval


    @classmethod
    def createFromInventory(cls, inventory_file):
        retval = cls()

        # Load Ansible inventory, use ansible's mechanism to merge variable from diffent levels
        loader = DataLoader()
        # Sources can be a single path or comma separated paths
        inventory = InventoryManager(loader=loader, sources=inventory_file)
        variable_manager = VariableManager(loader=loader, inventory=inventory)
        
        for host in inventory.hosts:
            hv = inventory.get_host(host).get_vars()
            h  = inventory.get_host(host)
            # Get host's vars
            host_vars = variable_manager.get_vars(host=h, task=None, include_hostvars=True, include_delegate_to=True, use_cache=True)
            print(json.dumps(host_vars, indent=4))

            # There variables are expected by VM machine definition
            # "name" - aka hostname
            # "template" - a VM template to clone from
            # "ram"
            # "cpu"
            # "scsi"
            #   - adapter
            # "disks"
            #   - 
            # "vmware"
            #   - vm_folder
            #   - dataloader
            # "network"
            #   - adapter
            # "addresses"
            name = host_vars['inventory_hostname_short']
            defaultMachine  = Machine(name)
            mdict = dict({'addresses': {}})
            if "template" in host_vars:
                mdict['template'] = host_vars['template']
            if "ram" in host_vars:
                mdict['ram'] = host_vars['ram']
            if "cpu" in host_vars:
                mdict['cpu'] = host_vars['cpu']
            if "scsi" in host_vars:
                mdict['scsi'] = host_vars['scsi']

            if "disks" in host_vars:
                mdict['disks'] = host_vars['disks']

            if "vmware" in host_vars:
                mdict['vmware'] = host_vars['vmware']

            if "network" in host_vars and host_vars['network']:
                mdict['network'] = host_vars['network']

            # Note: machine has key address (singular) while cluster has key addresses (plural)
            if "address" in host_vars and host_vars['address'] and isinstance(host_vars['address'], str):
                ip = host_vars['address']
                mdict['addresses'][name] = ip

            machine = defaultMachine.updateFromDict(mdict)
            retval.machines.append(machine)
            logging.debug('Machine loaded: {:<20} CPU: {:<2} RAM: {:<4} Storage: {}'
                          .format(machine.name
                                  , machine.cpu
                                  , machine.ram
                                  , str(machine.disks)
                              )
            )

            if 'cluster' in host_vars and not retval.cluster:
                logging.debug(host_vars['cluster'])
                cluster = host_vars['cluster']
                retval.cluster = Cluster.createFromDict(cluster)
            if retval.cluster:
                retval.cluster.nodes.append(name)

        return retval

    def validate(self, content):
        for m in self.machines:
            m.validate(content)


# Start program
if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout,
                        level=logging.DEBUG,
                        format='%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(message)s')

    c = VsCreadential.load()

    # parse yaml file
    ##cfg = Config.createFromYAML("rac-a.yaml")

    # parse yaml file
    ##cfg = Config.createFromYAML("rac-a.yaml")

    #cfg = Config.createFromYAML("rac-19.yaml")
    
    cfg = Config.createFromInventory("rac19-a.040.inventory.yml")

