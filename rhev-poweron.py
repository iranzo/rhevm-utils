#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for elastic management (EMS) of RHEV-H/RHEL hosts for
# RHEVM based on Douglas Schilling Landgraf <dougsland@redhat.com> scripts
# for ovirt (https://github.com/dougsland/ovirt-restapi-scripts.git)
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
# - Do not manage any host without tag elas_manage
# - Operate on one host per execution, exitting after each change
# - Have at least one host up without vm's to hold new VM's
# - Shutdown/suspend hosts without vm's until there's only one left
# - If a host has been put on maintenance and has no tag, it will not be activated by the script
# - Any active host must have no tags on it (that would mean user-enabled, and should have the tag removed)


# tags behaviour
#     elas_manage: manage this host by using the elastic management script (EMS)
#     elas_maint : this host has been put on maintenance by the EMS

import optparse
import os
import getpass
from random import choice

from ovirtsdk.xml import params
from rhev_functions import *


description = """
RHEV-Poweron is a script for managing via API the hypervisors under RHEV command, both RHEV-H and RHEL hosts.

It's goal is to activate the provided number of hosts per execution.

"""

# Option parsing
p = optparse.OptionParser("rhev-poweron.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="admin")
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option("-a", "--action", dest="action", help="Power action to execute", metavar="action", default="pm-suspend")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option('-b', "--batch", dest="batch", help="Batch number of hosts to return from maintenance", metavar='[0-n]',
             default=5, type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)

(options, args) = p.parse_args()

if options.askpassword:
    options.password = getpass.getpass("Enter password: ")

baseurl = "https://%s:%s" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


#FUNCTIONS
def activate_host(target):
    """Activates host from maintenance mode removing required tags"""
    # Activate    one host at a time...
    if options.verbosity > 0:
        print "Activating target %s" % target

    #Remove elas_maint TAG to host
    if not api.hosts.get(id=target).tags.get(name="elas_maint"):
        try:
            api.hosts.get(id=target).tags.get(name="elas_maint").delete()
        except:
            print "Error deleting tag elas_maint from host %s" % api.host.get(id=target).name

    if api.hosts.get(id=target).status.state == "maintenance":
        api.hosts.get(id=target).activate()

    #Get Host MAC
    for nic in api.hosts.get(id=target).nics.list():
        mac = nic.mac.get_address()
        # By default, send wol using every single nic at RHEVM host
        if mac != "":
            comando = "for tarjeta in $(for card in $(ls -d /sys/class/net/*/);do echo $(basename $card);done);do ether-wake -i $tarjeta %s ;done" % mac
            if options.verbosity >= 1:
                print "Sending %s the power on action via %s" % (target, mac)
            os.system(comando)

    return


def process_cluster(clusid):
    """Processes cluster"""
    enablable = []
    query = "status = maintenance and tag = elas_manage and tag = elas_main and cluster = %s" % api.clusters.get(id=clusid).name
    for host in listhosts(api, query):
        if host.status.state == "maintenance":
            if api.hosts.get(id=host.id).tags.get(name="elas_manage"):
                if api.hosts.get(id=host.id).tags.get(name="elas_maint"):
                    if options.verbosity >= 1:
                        print "Host %s is tagged as elas_maint and it's down, adding to activation list..." % host.id
                    enablable.append(host.id)

    number = 0

    while number < options.batch:
        number = number + 1
        victima = None
        try:
            victima = choice(enablable)
            enablable.remove(victima)
            if options.verbosity > 3:
                print "Enabling host %s" % victima
            activate_host(victima)
        except:
            if options.verbosity > 4:
                print "No more hosts to enable"

################################ MAIN PROGRAM ############################
#Sanity checks
if __name__ == "__main__":
    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster.id)
    else:
        process_cluster(api.clusters.get(name=options.cluster).id)
