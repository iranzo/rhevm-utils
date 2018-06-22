#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
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
# - Operate on one host per execution, exiting after each change
# - Have at least one host up without vm's to hold new VM's
# - Shutdown/suspend hosts without vm's until there's only one left
# - If a host has been put on maintenance and has no tag, it will not be activated by the script
# - Any active host must have no tags on it (that would mean user-enabled, and should have the tag removed)


# tags behaviour
# elas_manage: manage this host by using the elastic management script (EMS)
# elas_maint : this host has been put on maintenance by the EMS

import optparse
import os
from random import choice

from rhev_functions import *

description = """
RHEV-Elastic is a script for managing via API the hypervisors under RHEV command, both RHEV-H and RHEL hosts.

It's goal is to keep the higher amount of hosts turned off or suspended in
order to save energy, automatically activating or deactivating hosts when
needed in order to satisfy your environment needs.

"""

# Option parsing
p = optparse.OptionParser("rhev-elastic.py [arguments]", description=description)
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
p.add_option("-a", "--action", dest="action", help="Power action to execute", metavar="action", default="pm-suspend")
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
def deactivate_host(target):
    """Deactivates hosts putting it on maintenance and associating required tags
    @param target: Host ID to activate
    """
    host = api.hosts.get(id=target)
    # Shutting down one host at a time...
    if options.verbosity > 0:
        print("Shutting down target %s" % target)

    # Add elas_maint TAG to host
    host.tags.add(params.Tag(name="elas_maint"))

    # Set host on maintenance
    try:
        host.deactivate()
    except:
        print("Error deactivating host %s" % api.hosts.get(id=target).name)

    # Get host IP
    ip = host.address

    # Should wait until host state is 'maintenance'

    i = 0
    while i < 30:
        if api.hosts.get(id=target).status.state == "maintenance":
            if options.verbosity > 6:
                print("Host is now on maintenance...")
            i = 30
        else:
            if options.verbosity > 6:
                print("Host still not on maintenance... sleeping")
            time.sleep(2)
        i += 1

    if api.hosts.get(id=target).status.state == "maintenance":
        # Execute power action
        # /etc/pki/rhevm/keys/rhevm_id_rsa
        if options.verbosity >= 1:
            print("Sending %s the power action %s" % (host, options.action))

        comando = '/usr/bin/ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=10 -i ' \
                  '/etc/pki/ovirt-engine/keys/engine_id_rsa root@%s %s ' % (ip, options.action)

        os.system(comando)
        os.system(comando)
        os.system(comando)
    return


def activate_host(target):
    """Reactivates host by removing associated tags and leaving maintenance mode
    @param target: Host ID to activate
    """
    # Activate    one host at a time...
    if options.verbosity > 0:
        print("Activating target %s" % target)

    # Remove elas_maint TAG to host
    if not api.hosts.get(id=target).tags.get(name="elas_maint"):
        try:
            api.hosts.get(id=target).tags.get(name="elas_maint").delete()
        except:
            print("Error deleting tag elas_maint from host %s" % api.host.get(id=target).name)

    if api.hosts.get(id=target).status.state == "maintenance":
        api.hosts.get(id=target).activate()

    # Get Host MAC
    for nic in api.hosts.get(id=target).nics.list():
        mac = nic.mac.get_address()
        # By default, send wol using every single nic at RHEVM host
        if mac != "":
            comando = "for tarjeta in $(for card in $(ls -d /sys/class/net/*/);do echo $(basename $card);done);do " \
                      "ether-wake -i $tarjeta %s ;done" % mac
            if options.verbosity >= 1:
                print("Sending %s the power on action via %s" % (target, mac))
            os.system(comando)

    return


def process_cluster(clusid):
    """Processes cluster
    @param clusid: Identifies Cluster ID to process
    """
    if options.verbosity > 1:
        print("\nProcessing cluster with id %s and name %s" % (clusid, api.clusters.get(id=clusid).name))
        print("#############################################################################")

    # Emptying maintanable and activable hosts list
    maintable = []
    enablable = []
    maintable_prio = []

    hosts_total = 0
    hosts_up = 0
    hosts_maintenance = 0
    hosts_other = 0
    hosts_without_vms = 0
    hosts_with_vms = 0

    query = "cluster = %s" % api.clusters.get(id=clusid).name
    for host in paginate(api.hosts, query):
        if host.tags.get(name="elas_manage"):
            vms = api.hosts.get(id=host.id).summary.total
            status = "discarded"
            inc = 1

            if host.cluster.id != clusid:
                # Not process this host if doesn't pertain to cluster
                if options.verbosity >= 3:
                    print("Host %s doesn't pertain to cluster %s, discarding" % (host.id, clusid))
            else:
                # Preparing list of valid hosts
                if vms == 0:
                    if host.status.state == "up":
                        maintable.append(host.id)
                        status = "accepted"
                        if api.hosts.get(id=host.id).storage_manager.valueOf_ != "true":
                            maintable_prio.append(host.id)
                    if host.status.state == "maintenance":
                        if host.tags.get(name="elas_maint"):
                            enablable.append(host.id)
                            status = "accepted"
                        else:
                            status = "No elas_maint tag discarded"
                            inc = 0
                if options.verbosity >= 2:
                    print("Host (%s) %s with %s vms detected with status %s and spm status %s (%s for operation)" % (
                        host.name, host.id, vms, api.hosts.get(id=host.id).status.state,
                        api.hosts.get(id=host.id).storage_manager.valueOf_, status))

                # Counters
                hosts_total += inc

                if host.status.state == "up":
                    hosts_up += inc
                    if vms == 0:
                        hosts_without_vms += inc
                    else:
                        hosts_with_vms += inc
                else:
                    if host.status.state == "maintenance":
                        hosts_maintenance += inc
                    else:
                        hosts_other += inc

    if options.verbosity >= 1:
        if hosts_total > 0:
            print("\nHost list to manage:")
            print("\tCandidates to maintenance: %s" % maintable)
            print("\tPriority to maintenance: %s" % maintable_prio)
            print("\tCandidates to activation:    %s" % enablable)
            print("\nHosts TOTAL (Total/Up/Maintenance/other): %s/%s/%s/%s" % (
                hosts_total, hosts_up, hosts_maintenance, hosts_other))
            print("Hosts        UP (with VM's/ without):    %s/%s" % (hosts_with_vms, hosts_without_vms))
        else:
            print("\nNo hosts in cluster %s, skipping" % clusid)

    # CODE TO CHECK HOST COUNT, Host still active, etc
    # Useful vars:     hosts_total,hosts_up,hosts_maintenance,hosts_other,hosts_with_vms,hosts_without_vms
    # Useful arrays: enablable / maintable

    # ENABLE SECTION

    # At least one host but no one is up -> enable one host
    if hosts_total > 0 and hosts_up == 0:
        try:
            target = choice(enablable)
            if options.verbosity >= 2:
                print("\nActivating host %s because no one is up\n" % target)
            activate_host(target)
            return 0
        except:
            if options.verbosity >= 1:
                print("\nNo host to enable\n")
            return 1

    # Host active without vm's
    if hosts_up > 0:
        # At least one host up without vm's:
        if hosts_without_vms == 0:
            try:
                target = choice(enablable)
                if options.verbosity >= 2:
                    print("\nActivating host %s because there are no hosts without vm's\n" % target)

                activate_host(target)
                return 0
            except:
                if options.verbosity >= 1:
                    print("\nNo host to enable\n")
                return 1

    # DISABLE SECTION
    if hosts_without_vms > 1:
        # More than one host without VM's so we can shutdown one
        if len(maintable) != 0:
            if len(maintable_prio) != 0:
                target = choice(maintable_prio)
            else:
                target = choice(maintable)
            if options.verbosity >= 2:
                print("\nPutting host %s into maintenance because there are more than 1 host without vm's\n" % target)
            deactivate_host(target)
            return 0
        else:
            print("\nNo host to put into maintenance\n")
            return 1

    # NOTHING TO DO SECTIOn

    if options.verbosity >= 2:
        print("\nNothing to do as enable/disable scripts conditions are not met")

    return


# MAIN PROGRAM
if __name__ == "__main__":
    # Check if we have defined needed tags and create them if missing
    check_tags(api, options)

    # TAGALL?
    # Add elas_maint TAG to every single host to automate the management
    if options.tagall == 1:

        if options.verbosity >= 1:
            print("Tagging all hosts with elas_manage")

        for host in paginate(api.hosts):
            try:
                host.tags.add(params.Tag(name="elas_manage"))
            except:
                print("Error adding elas_manage tag to host %s" % host.name)

    # Sanity checks
    # Check hosts with elas_maint tag and status active
    query = "status = up"
    for host in paginate(api.hosts, query):
        if host.status.state == "up":
            if api.hosts.get(id=host.id).tags.get(name="elas_maint"):
                if options.verbosity >= 1:
                    print("Host %s is tagged as elas_maint and it's active, removing tag..." % host.id)
                api.hosts.get(id=host.id).tags.get(name="elas_maint").delete()

    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster.id)
    else:
        process_cluster(api.clusters.get(name=options.cluster).id)
