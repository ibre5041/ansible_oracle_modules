from pyVmomi import vim, vmodl

def wait_for_tasks(service_instance, tasks):
    """Given the service instance si and tasks, it returns after all the tasks are complete
    """
    property_collector = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]
    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                 for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                               pathSet=[],
                                                               all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]
    pcfilter = property_collector.CreateFilter(filter_spec, True)
    try:
        version, state = None, None
        # Loop looking for updates till the state moves to a completed state.
        while len(task_list):
            update = property_collector.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    for change in obj_set.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

                        if not str(task) in task_list:
                            continue

                        if state == vim.TaskInfo.State.success:
                            # Remove task from taskList
                            task_list.remove(str(task))
                        elif state == vim.TaskInfo.State.error:
                            raise task.info.error
            # Move to next version
            version = update.version
    finally:
        if pcfilter:
            pcfilter.Destroy()

def get_obj(content, vimtype, name):
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj

def get_resourcePools(entity):
   pools = []
   for pool in entity.resourcePool:
      pools += get_resourcePools(pool)
   pools.append(entity)
   return pools

import dns.reversename
import dns.update
import dns.query
import dns.tsigkeyring

import logging

def create_dns_record(new_hostname, domain, new_ipaddress):
    PRIMARY_DNS_SERVER_IP = '192.168.8.200'
    TTL = 300

    keyring = dns.tsigkeyring.from_text({
        "dynamic.vmware.haf.": "jn694IwJ9IP4i5yGtSdIZJTFeFpVEvK2wa78gHVX8PohLNBQVYQd+JyGNX8A3hju8WmsNVo1Oq58YS93HR4HIQ=="
    })
    
    logging.debug("DNS record A")
    ### Create A Record
    # Set the domain name with a trailing dot (to stop auto substitution of zone)
    dns_domain = '%s.' % (domain)
    # Prepare the payload for DNS record update in the given zone/domain (dns_domain)

    logging.debug(" {} ({})".format(new_hostname, new_ipaddress))
    update = dns.update.Update(zone=dns_domain
                               , keyname='dynamic.vmware.haf.'
                               , keyring=keyring
                               , keyalgorithm=dns.tsig.HMAC_SHA512)
    # Inject the record details into the dns.update.Update class
    update.replace(new_hostname, TTL, 'A', new_ipaddress)
    # Submit the new record to the DNS server to apply the update
    response = dns.query.tcp(update, PRIMARY_DNS_SERVER_IP, timeout=5)
    flags = dns.flags.to_text(response.flags)
    logging.debug(" A   DNS update response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))

    logging.debug("DNS record PTR")
    ### Create reverse entry (PTR)
    # Neat function to generate a reverse entry
    reventry = dns.reversename.from_address(new_ipaddress)
    revzone = ''
    # Specify the reverse lookup zone based on the reverse IP address.
    # The labels[X:] property allows you to specify which octet to use.
    # e.g. 3: will apply the record to the 10.in-addr.arpa zone, 
    # whereas 1: will apply it to the 72.23.10.in-addr.arpa zone
    revzone = b'.'.join(dns.name.from_text(str(reventry)).labels[1:]) # 
    revzone = revzone.decode()

    # Prepare the payload for the DNS record update
    raction = dns.update.Update(zone=revzone
                                , keyname='dynamic.vmware.haf.'
                                , keyring=keyring
                                , keyalgorithm=dns.tsig.HMAC_SHA512)

    # Although we are updating the reverse lookup zone, 
    # the record needs to point back to the ‘test.example.com’ domain, not the 10.in-addr.arpa domain
    new_host_fqdn = '%s.%s' % (new_hostname, dns_domain)
    # Inject the updated record details into the the class, preparing for submission to the DNS server
    raction.replace(reventry, TTL, dns.rdatatype.PTR, new_host_fqdn)
    # submit the new record to the DNS server to apply the update
    response = dns.query.tcp(raction, PRIMARY_DNS_SERVER_IP, timeout=5)
    flags = dns.flags.to_text(response.flags)
    logging.debug(" PTR DNS update response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))


def add_dns_record(new_hostname, domain, new_ipaddress):
    PRIMARY_DNS_SERVER_IP = '192.168.8.200'
    TTL = 300

    keyring = dns.tsigkeyring.from_text({
        "dynamic.vmware.haf.": "jn694IwJ9IP4i5yGtSdIZJTFeFpVEvK2wa78gHVX8PohLNBQVYQd+JyGNX8A3hju8WmsNVo1Oq58YS93HR4HIQ=="
    })
    
    logging.debug("DNS record A")
    ### Create A Record
    # Set the domain name with a trailing dot (to stop auto substitution of zone)
    dns_domain = '%s.' % (domain)
    # Prepare the payload for DNS record update in the given zone/domain (dns_domain)

    logging.debug(" {} ({})".format(new_hostname, new_ipaddress))
    update = dns.update.Update(zone=dns_domain
                               , keyname='dynamic.vmware.haf.'
                               , keyring=keyring
                               , keyalgorithm=dns.tsig.HMAC_SHA512)
    # Inject the record details into the dns.update.Update class
    update.add(new_hostname, TTL, 'A', new_ipaddress)
    # Submit the new record to the DNS server to apply the update
    response = dns.query.tcp(update, PRIMARY_DNS_SERVER_IP, timeout=5)
    flags = dns.flags.to_text(response.flags)
    logging.debug(" A   DNS update response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))


def delete_dns_record(host, domain, ip):
    PRIMARY_DNS_SERVER_IP = '192.168.8.200'

    keyring = dns.tsigkeyring.from_text({
        "dynamic.vmware.haf.": "jn694IwJ9IP4i5yGtSdIZJTFeFpVEvK2wa78gHVX8PohLNBQVYQd+JyGNX8A3hju8WmsNVo1Oq58YS93HR4HIQ=="
    })

    dns_domain = '%s.' % (domain)

    logging.debug("DNS records A")
    logging.debug(" {} ({})".format(host, ip))
    update = dns.update.Update(zone=dns_domain
                               , keyname='dynamic.vmware.haf.'
                               , keyring=keyring
                               , keyalgorithm=dns.tsig.HMAC_SHA512)

    update.delete(host, 'A')
    response = dns.query.tcp(update, PRIMARY_DNS_SERVER_IP)
    flags = dns.flags.to_text(response.flags)
    logging.debug(" A   DNS delete response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))

    update.delete(host, 'TXT')
    response = dns.query.tcp(update, PRIMARY_DNS_SERVER_IP)
    flags = dns.flags.to_text(response.flags)
    logging.debug(" TXT DNS delete response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))

    if ip:
        ### Create reverse entry (PTR)
        # Neat function to generate a reverse entry
        reventry = dns.reversename.from_address(ip)
        revzone = ''
        # Specify the reverse lookup zone based on the reverse IP address.
        # The labels[X:] property allows you to specify which octet to use.
        # e.g. 3: will apply the record to the 10.in-addr.arpa zone, 
        # whereas 1: will apply it to the 72.23.10.in-addr.arpa zone
        revzone = b'.'.join(dns.name.from_text(str(reventry)).labels[1:]) # 
        revzone = revzone.decode()
        # Prepare the payload for the DNS record update
        raction = dns.update.Update(zone=revzone
                                    , keyname='dynamic.vmware.haf.'
                                    , keyring=keyring
                                    , keyalgorithm=dns.tsig.HMAC_SHA512)

        # Although we are updating the reverse lookup zone, 
        # the record needs to point back to the ‘test.example.com’ domain, not the 10.in-addr.arpa domain
        host_fqdn = '%s.%s' % (host, dns_domain)
        # Inject the updated record details into the the class, preparing for submission to the DNS server
        raction.delete(reventry, dns.rdatatype.PTR)
        # submit the new record to the DNS server to apply the update
        response = dns.query.tcp(raction, PRIMARY_DNS_SERVER_IP, timeout=5)
        flags = dns.flags.to_text(response.flags)
        logging.debug(" PTR DNS delete response: {} {}".format(dns.rcode.to_text(response.rcode()), flags))
