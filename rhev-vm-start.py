#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for starting VM'susing rhevm-sdk
# api based on single VM dependency
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
# - reverse missing -> start VM specified
# - reverse 1             -> start all VM's if VM specified is up and running

# tags behaviour
#     elas_manage: this machine is being managed by this script


import sys
import optparse
import getpass

from ovirtsdk.xml import params
from rhev_functions import *

description = """
RHEV-vm-start is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's started if another VM is running and host status has not changed

"""

# Option parsing
p = optparse.OptionParser("rhev-vm-start.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="admin")
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option('-t', "--tagall", dest="tagall", help="Tag all hosts with elas_manage", metavar='0/1', default=0,
             type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)
p.add_option('-m', "--machine", dest="machine", help="Machine name beggining", metavar="machine", default=None)
p.add_option('-r', "--reverse", dest="reverse", help="Reverse behaviour with machine name", metavar="reverse",
             default=0)

(options, args) = p.parse_args()

if options.askpassword:
    options.password = getpass.getpass("Enter password: ")

baseurl = "https://%s:%s" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


#FUNCTIONS
def process_cluster(cluster):
    """Processes cluster"""
    # Emtpy vars for further processing
    hosts_in_cluster = []
    vms_in_cluster = []
    tags_in_cluster = []
    tags_vm = {}
    tags_with_more_than_one = []

    # Get host list from this cluster
    query = "cluster = %s" % api.clusters.get(id=cluster.id).name
    for host in listhosts(api, query):
        if host.cluster.id == cluster.id:
            hosts_in_cluster.append(host.id)

    if options.verbosity > 2:
        print("\nProcessing cluster %s..." % cluster.name)
        print("##############################################")

    #Populate the list of tags and VM's
    query = "cluster = %s" % api.clusters.get(id=cluster.id).name
    for vm in listvms(api, query):
        if vm.cluster.id == cluster.id:
            vms_in_cluster.append(vm.id)

    query = "cluster = %s and tag = elas_manage" % api.clusters.get(id=cluster.id).name
    for vm in listvms(api, query):
        if vm.cluster.id == cluster.id:
            if vm.tags.get("elas_manage"):
                # Add the VM Id to the list of VMS to manage in this cluster
                vms_in_cluster.append(vm.id)

    if options.verbosity > 3:
        print("Hosts in cluster:")
        print(hosts_in_cluster)

        print("Vm's in cluster")
        print(vms_in_cluster)

    destino = None
    for vm in vms_in_cluster:
        # Iterate until we get our target machine to monitor
        maquina = api.vms.get(id=vm)
        largo = len(options.machine)
        if maquina.name.startswith(options.machine):
            if maquina.tags.get("elas_manage"):
                destino = maquina
            else:
                if options.verbosity > 4:
                    print("Specified target machine has no elas_manage tag attached")
                sys.exit(1)

    # Iterate for all the machines in our cluster and check behaviour based on reverse value
    if destino:
        for vm in vms_in_cluster:
            if options.reverse == 0:
                if destino.status.state == "down":
                    if options.verbosity > 3:
                        print("Our VM is down... try to start it if possible")
                    one_is_up = False
                    for host in hosts_in_cluster:
                        if api.hosts.get(id=host).status.state == "up":
                            one_is_up = True
                    if one_is_up:
                        try:
                            destino.start()
                        except:
                            if options.verbosity > 3:
                                print("Error starting up machine %s" % destino.name)
            else:
                # Reverse is != 0... then just boot if target machine is already up
                if destino.status.state == "up":
                    # Our target VM is not down, it's safe to start our machines up!
                    for vm in vms_in_cluster:
                        maquina = api.vms.get(id=vm)
                        if maquina.tags.get("elas_manage"):
                            if maquina.status.state != "up":
                                if maquina.id != destino.id:
                                    try:
                                        maquina.start()
                                    except:
                                        if options.verbosity > 3:
                                            print("Error starting %s" % maquina.name)
                        else:
                            if options.verbosity > 4:
                                print("VM %s has no elas_manage tag associated" % maquina.name)
                else:
                    if options.verbosity > 3:
                        print("Target machine is not up, not starting vm")

################################ MAIN PROGRAM ############################
if __name__ == "__main__":
    #Check if we have defined needed tags and create them if missing
    check_tags(api, options)

    # TAGALL?
    #Add elas_maint TAG to every single vm to automate the management
    if options.tagall == 1:
        if options.verbosity >= 1:
            print("Tagging all VM's with elas_manage")
        for vm in listvms(api):
            try:
                vm.tags.add(params.Tag(name="elas_manage"))
            except:
                print("Error adding elas_manage tag to vm %s" % vm.name)
    if options.machine == "":
        print("Error machine name must be defined")
        sys.exit(1)

    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster)
    else:
        process_cluster(api.clusters.get(name=options.cluster))
