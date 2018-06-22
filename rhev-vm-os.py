#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
#
# Description: Script for VM's grouping/ungrouping using rhevm-sdk
# api based on O.S. and Host load
#
# Requires rhevm-sdk to work
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.

# Goals:
# - Do not manage any VM without tag elas_manage
# - Group machines with same O.S. at same hosts

# tags behaviour
# elas_manage: manage this VM by using the elastic management script (EMS)


import optparse

from rhev_functions import *

description = """
RHEV-vm-os is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's <-> host <-> O.S.    to group VM's using same O.S. to take benefit of KSM within nodes
at the same physical host.

"""

# Option parsing
p = optparse.OptionParser("rhev-vm-os.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="admin")
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option('-t', "--tagall", dest="tagall", help="Tag all hosts with elas_manage", metavar='0/1', default=0,
             type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


# FUNCTIONS
def process_cluster(cluster):
    """Processes cluster
    @param cluster: Cluster name to process
    """
    # Emtpy vars for further processing
    hosts_in_cluster = []
    vms_in_cluster = []
    tags_os = {}

    # Get host list from this cluster
    query = "cluster = %s and status = up" % api.clusters.get(id=cluster.id).name
    for host in paginate(api.hosts, query):
        if host.cluster.id == cluster.id:
            if host.status.state == "up":
                hosts_in_cluster.append(host.id)

    if options.verbosity > 2:
        print("\nProcessing cluster %s..." % cluster.name)
        print("##############################################")

    # Create the empty set of vars that we'll populate later
    query = "cluster = %s and status = up" % api.clusters.get(id=cluster.id).name
    for vm in paginate(api.vms, query):
        if vm.status.state == "up":
            if vm.cluster.id == cluster.id:
                tags_os[vm.os.type_] = []

    # Populate the list of tags and VM's
    query = "cluster = %s and status = up and tag = elas_manage" % api.clusters.get(id=cluster.id).name
    for vm in paginate(api.vms, query):
        if vm.cluster.id == cluster.id:
            if vm.status.state == "up":
                if not vm.tags.get("elas_manage"):
                    if options.verbosity > 3:
                        print("VM %s is discarded because it has no tag elas_manage" % vm.name)
                else:
                    # Add the VM Id to the list of VMS to manage in this cluster
                    vms_in_cluster.append(vm.id)
                    tags_os[vm.os.type_].append(vm.name)

        # Remove duplicates...
        tags_os[vm.os.type_] = list(set(tags_os[vm.os.type_]))

    # Sort the tags by the number of elements in it
    sorted_tags_os = sorted(tags_os.iteritems(), key=lambda x: x[1], reverse=True)

    # Print tags/vm's distribution
    if options.verbosity > 3:
        print("OS/VM's")
        print(sorted_tags_os)
        print("Hosts in cluster")
        print(hosts_in_cluster)

    # VM's to process:
    vms_to_process = []

    for vm in vms_in_cluster:
        if api.vms.get(id=vm).cluster.id == cluster.id:
            vms_to_process.append(api.vms.get(id=vm).name)

    if options.verbosity > 3:
        print("VM's to process")
        print(vms_to_process)

    sorted_tag = []

    for vm in vms_to_process:
        sorted_tag.append(api.vms.get(name=vm).os.type_)

    # Order the tags based on VM ordering (using the other function    "list(set(sorted_tag))" made it fail as
    # ordering changed)
    ordered_tags = []
    i = 0
    while i < len(sorted_tag):
        tag = sorted_tag[i]
        if tag not in ordered_tags:
            ordered_tags.append(tag)
        i += 1

    sorted_tag = ordered_tags

    i = 0
    while i < len(sorted_tag):
        hosts_used = []
        # Sort the tags
        etiqueta = sorted_tag[i]
        if options.verbosity > 1:
            print("Processing tag %s" % etiqueta)

        # start with bigger set of tag
        for host in hosts_in_cluster:
            if options.verbosity > 5:
                print("Processing host %s" % api.hosts.get(id=host).name)
            for vm in vms_to_process:
                if api.vms.get(name=vm).os.type_ == etiqueta:
                    if options.verbosity > 6:
                        print("Processing vm %s" % vm)
                    maquina = api.vms.get(name=vm)
                    if maquina.status.state == "up":
                        if maquina.host.id == host:
                            if options.verbosity > 6:
                                print("VM %s is already on processed host, skipping" % maquina.name)
                        else:
                            if maquina.host.id in hosts_used:
                                if options.verbosity > 5:
                                    print("VM %s is on already processed host, skipping" % maquina.name)
                            else:
                                if options.verbosity > 5:
                                    print("VM can be processed (not already in processed hosts)")

                                host_free = api.hosts.get(id=host).max_scheduling_memory
                                if host_free > vmused(api, maquina):
                                    # We've free space, move in there...
                                    if options.verbosity > 2:
                                        print("Enough memory on %s to migrate %s" % (
                                            api.hosts.get(id=host).name, maquina.name))
                                    migra(api, options, maquina, params.Action(host=api.hosts.get(id=host)))

                                else:
                                    if options.verbosity > 5:
                                        print("Not enought RAM, let's try to make more room...")
                                        # Not enough ram, let's see if we can kick out other O.S. VM's
                                        # from this Host to make room

                                    # Fill list of OS already processed to avoid them
                                    os_not_to_excomulgate = []
                                    j = 0

                                    while j <= i:
                                        os_not_to_excomulgate.append(sorted_tag[j])
                                        j += 1

                                    # Fill list with vms that can be moved away
                                    vms_to_excomulgate = []
                                    query = "status = up and host = %s" % host
                                    for virtual in paginate(api.vms, query):
                                        if virtual.status.state == "up":
                                            if virtual.host.id == host:
                                                if virtual.os.type_ not in os_not_to_excomulgate:
                                                    vms_to_excomulgate.append(virtual.name)

                                    if options.verbosity > 5:
                                        print("OS. already processed: %s" % os_not_to_excomulgate)
                                        print("VM's to excomulgate: %s\n" % vms_to_excomulgate)

                                    fits_in_ram = False
                                    host_free = api.hosts.get(id=host).max_scheduling_memory
                                    mem_to_free = host_free
                                    for virtual in vms_to_excomulgate:
                                        mem_to_free = mem_to_free + vmused(api, api.vms.get(name=virtual))
                                        if mem_to_free >= vmused(api, maquina):
                                            fits_in_ram = True

                                    if options.verbosity > 6:
                                        print("Mem that will be freed by excomulgating hosts %s" % mem_to_free)
                                        print("Mem required for VM %s" %
                                              maquina.statistics.get("memory.installed").values.value[0].datum)

                                    if fits_in_ram:
                                        keeplooping = True
                                    else:
                                        keeplooping = False

                                    while keeplooping:

                                        victima = None
                                        for virtual in vms_to_excomulgate:
                                            # We've one machine to excomulgate so let's do it
                                            if not victima:
                                                victima = virtual
                                            if vmused(api, api.vms.get(name=virtual)) > vmused(api, api.vms.get(
                                                    name=victima)):
                                                victima = virtual

                                        # Machine with higher ram usage has been selected, move it away to make room
                                        # for the next one to enter
                                        if victima:
                                            if options.verbosity > 5:
                                                print("Target machine to migration is %s" % victima)
                                            vms_to_excomulgate.remove(victima)
                                            migra(api, options, api.vms.get(name=victima))

                                        host_free = api.hosts.get(id=host).max_scheduling_memory
                                        if host_free > vmused(api, maquina):
                                            # Enough RAM, exit loop to start moving in a new machine, if not,
                                            # keep running to make more room
                                            keeplooping = False

                                        if not vms_to_excomulgate:
                                            # No more VM's to excomulgate, exit loop
                                            keeplooping = False
                                        if keeplooping:
                                            if options.verbosity > 5:
                                                print("Still not enough RAM available... repeating process")

                                    # Check new ram status

                                    # MV moved away, recheck ram to make it fit
                                    host_free = api.hosts.get(id=host).max_scheduling_memory

                                    if options.verbosity > 5:
                                        print("Host free RAM %s" % host_free)
                                        print("VM required RAM %s" % vmused(api, maquina))

                                    if host_free > vmused(api, maquina):
                                        migra(api, options, maquina, params.Action(host=api.hosts.get(id=host)))
                                    else:
                                        if options.verbosity > 2:
                                            print("Not enough ram, hopping to next host")
            hosts_used.append(host)
        i += 1
    return

# MAIN PROGRAM
if __name__ == "__main__":
    # Check if we have defined needed tags and create them if missing
    check_tags(api, options)

    # TAGALL?
    # Add elas_maint TAG to every single vm to automate the management
    if options.tagall == 1:
        if options.verbosity >= 1:
            print("Tagging all VM's with elas_manage")
        for vm in paginate(api.vms):
            try:
                vm.tags.add(params.Tag(name="elas_manage"))
            except:
                print("Error adding elas_manage tag to vm %s" % vm.name)

    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster)
    else:
        process_cluster(api.clusters.get(name=options.cluster))
