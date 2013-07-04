#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for automatic RHEV-H hypervisor upgrade when there's a new
# version available on RHEV-M
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
# - Automatically put RHEV-H hosts on maintenace for upgrade
# - Once on maintenance, deploy updated install image
# - After timeout, set host to active (actual bug in RHEV)

# tags behaviour
#     elas_manage:  manage this host by using the elastic management script (EMS)
#     elas_upgrade: this host status has been set by automatic upgrade, so it can be installed/activated
#     elas_maint:   this host status has been set by rhev-elastic, so it can be installed/activated

import sys
import getopt
import optparse
import os
import time
import glob

from ovirtsdk.api import API
from ovirtsdk.xml import params
from random import choice
from rhev_functions import *

description = """
RHEV-hypervisor-autoupgrade is a script for automatically upgrade RHEV-H hosts under RHEV

It's goal is to try upgrading each host one after one, starting with the
ones with no VM's running on them.

"""

# Option parsing
p = optparse.OptionParser("rhev-hypevisor-autoupgrade.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option("-a", "--action", dest="action", help="Power action to execute", metavar="action", default="pm-suspend")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)
p.add_option('-t', "--tagall", dest="tagall", help="Tag all hosts with elas_manage", metavar='0/1', default=0, type='int')
p.add_option('-r', "--release", dest="release", help="Select release to deploy. Like 20130528.0.el6_4", metavar='release', default="latest")
p.add_option('-d', "--delay", dest="delay", help="Set delay to way until activation after install is sent", metavar='delay', default=900)

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True)


#FUNCTIONS
def upgrade_host(target):
    """Deactivates hosts putting it on maintenance and associating required tags before upgrading"""
    host = api.hosts.get(id=target)
    # Shutting down one host at a time...
    if options.verbosity > 0:
        print "Preparing target %s" % target

    #Add elas_maint TAG to host
    host.tags.add(params.Tag(name="elas_upgrade"))

    #Set host on maintenance
    try:
        host.deactivate()
    except:
        print "Error deactivating host %s" % api.hosts.get(id=target).name

    #Get host IP
    ip = host.address

    #Should wait until host state is 'maintenance'

    i = 0
    while i < 30:
        if api.hosts.get(id=target).status.state == "maintenance":
            if options.verbosity > 6:
                print "Host is now on maintenance..."
            i = 30
        else:
            if options.verbosity > 6:
                print "Host still not on maintenance... sleeping"
            time.sleep(2)
        i = i + 1

    if api.hosts.get(id=target).status.state == "maintenance":
        #Execute upgrade for host with latest available version
        image = "%s" % get_max_version()
        try:
            print "Trying to upgrade %s" % host.name
            host.install(params.Action(image=image))
        except:
            print "Host failed to install"

        i = 0
        while i < options.delay:
            if api.hosts.get(id=target).status.state == "up":
                if options.verbosity > 6:
                    print "Host is now up again..."
                i = options.delay
            else:
                if options.verbosity > 6:
                    print "Host still not on maintenance... sleeping"
                time.sleep(1)
            i = i + 1

        # if host is listed as installation failed, enable it as this is a pending BZ
        if api.hosts.get(id=target).status.state == "install_failed":
            api.hosts.get(id=target).activate()

        # Remove tags no longer used
        api.hosts.get(id=host.id).tags.get(name="elas_upgrade").delete()
        api.hosts.get(id=host.id).tags.get(name="elas_maint").delete()

    return


def get_max_version():
    """Get maximum hipervisor version, checking first on disk, and if not, on higher version from hypervisors"""

    version = None

    available = []
    # Check all available hypervisor versions on disk (only on RHEV-M host)
    for fichero in glob.glob("/usr/share/rhev-hypervisor/rhevh*.iso"):
        file = fichero.split("/")[-1]
        available.append(file)

    try:
        version = sorted(available, key=lambda x: x[1], reverse=False)[0]
    except:
        version = None
    #Couldn't get version from disk, get it from the API
    if not version:
        versions = []
        releases = []
        # FIXME only query rhev-h hosts
        for host in listhosts(api, oquery=""):
            version = host.os.version.full_version.split("-")[1].strip()  # 20130528.0.el6_4
            release = host.os.version.full_version.split("-")[0].strip()  # 6.4
            if version not in versions:
                versions.append(version)
            if release not in releases:
                releases.append(release)
        try:
            version = "rhevh-%s-%s.iso" % (sorted(releases, key=lambda x: x[1], reverse=False)[0], sorted(versions, key=lambda x: x[1], reverse=False)[0])
        except:
            version = None

    return version


def process_cluster(clusid):
    """Processes cluster"""
    if options.verbosity > 1:
        print "\nProcessing cluster with id %s and name %s" % (clusid, api.clusters.get(id=clusid).name)
        print "#############################################################################"

    #Emptying maintanable and activable hosts list
    upgradable = []
    enablable = []
    upgradable_prio = []

    hosts_total = 0
    hosts_up = 0
    hosts_maintenance = 0
    hosts_maintenance_prio = 0
    hosts_other = 0
    hosts_without_vms = 0
    hosts_with_vms = 0

    version = get_max_version()

    # FIXME: only RHEV-H hosts
    query = "cluster = %s" % api.clusters.get(id=clusid).name
    for host in listhosts(api, query):
        if host.tags.get(name="elas_manage"):
            vms = api.hosts.get(id=host.id).summary.total
            status = "discarded"
            inc = 1

            if host.cluster.id != clusid:
                # Not process this host if doesn't pertain to cluster
                if options.verbosity >= 3:
                    print "Host %s doesn't pertain to cluster %s, discarding" % (host.id, clusid)
            else:
                #Preparing list of valid hosts
                hostver = "rhevh-%s-%s.iso" % (host.os.version.full_version.split("-")[0].strip(), host.os.version.full_version.split("-")[1].strip())
                if version > hostver:
                    status = "accepted upgrading from %s to %s" % (hostver, version)
                    if host.status.state == "up":
                        upgradable.append(host.id)

                        # Prioritize non-SPM host and hosts without VM's
                        if api.hosts.get(id=host.id).storage_manager.valueOf_ != "true" or vms == 0:
                            upgradable_prio.append(host.id)

                    if host.status.state == "maintenance":
                        # Add to prio list hosts set to maintenance by rhev-elastic
                        if host.tags.get(name="elas_maint") or host.tags.get(name="elas_upgrade"):
                            upgradable.append(host.id)
                            upgradable_prio.append(host.id)
                        else:
                            status = "No elas_maint tag discarded"
                            inc = 0

                else:
                    # Host already upgraded
                    status = "already done"

                if options.verbosity >= 2:
                    print "Host (%s) %s with %s vms detected with status %s and spm status %s (%s for operation)" % (host.name, host.id, vms, api.hosts.get(id=host.id).status.state, api.hosts.get(id=host.id).storage_manager.valueOf_, status)

                #Counters
                hosts_total = hosts_total + inc

                if host.status.state == "up":
                    hosts_up = hosts_up + inc
                    if vms == 0:
                        hosts_without_vms = hosts_without_vms + inc
                    else:
                        hosts_with_vms = hosts_with_vms + inc
                else:
                    if host.status.state == "maintenance":
                        hosts_maintenance = hosts_maintenance + inc
                    else:
                        hosts_other = hosts_other + inc

    if options.verbosity >= 1:
        if hosts_total > 0:
            print "\nMax version: %s" % version
            print "\nHost list to manage:"
            print "\tCandidates to upgrade: %s" % upgradable
            print "\tPriority to upgrade: %s" % upgradable_prio
            print "\nHosts TOTAL (Total/Up/Maintenance/other): %s/%s/%s/%s" % (hosts_total, hosts_up, hosts_maintenance, hosts_other)
            print "Hosts        UP (with VM's/ without):    %s/%s" % (hosts_with_vms, hosts_without_vms)
        else:
            print "\nNo hosts in cluster %s, skipping" % clusid

    #### CODE TO CHECK HOST COUNT, Host still active, etc

    #Useful vars:     hosts_total,hosts_up,hosts_maintenance,hosts_other,hosts_with_vms,hosts_without_vms
    #Useful arrays: enablable / upgradable

    ############################### UPGRADE SECTION ########################################
    if len(upgradable) != 0:
        if len(upgradable_prio) != 0:
            target = choice(upgradable_prio)
        else:
            target = choice(upgradable)
        if options.verbosity >= 2:
            print "\nPutting host %s into upgrade because there are more than 1 host without vm's\n" % target
        upgrade_host(target)
        return 0
    else:
        print "\nNo host to put into maintenance for upgrade\n"
        return 1

    ############################# NOTHING TO DO SECTION ###################################

    if options.verbosity >= 2:
        print "\nNothing to do as enable/disable scripts conditions are not met"

    return


################################ MAIN PROGRAM ############################
if __name__ == "__main__":
    #Check if we have defined needed tags and create them if missing
    check_tags(api, options)

    # TAGALL?
    #Add elas_upgrade TAG to every single host to automate the management
    if options.tagall == 1:

        if options.verbosity >= 1:
            print "Tagging all hosts with elas_manage"

        for host in listhosts(api):
            try:
                host.tags.add(params.Tag(name="elas_manage"))
            except:
                print "Error adding elas_manage tag to host %s" % host.name

    #Sanity checks
    ## Check hosts with elas_upgrade tag and status active
    query = "tag = elas_upgrade and status = up"
    for host in listhosts(api, query):
        if host.status.state == "up":
            if api.hosts.get(id=host.id).tags.get(name="elas_upgrade"):
                if options.verbosity >= 1:
                    print "Host %s is tagged as elas_upgrade and it's active, removing tag..." % host.id
                api.hosts.get(id=host.id).tags.get(name="elas_upgrade").delete()

    ## Check hosts with elas_maint tag and status active
    query = "tag = elas_maint and status = up"
    for host in listhosts(api, query):
        if host.status.state == "up":
            if api.hosts.get(id=host.id).tags.get(name="elas_maint"):
                if options.verbosity >= 1:
                    print "Host %s is tagged as elas_maint and it's active, removing tag..." % host.id
                api.hosts.get(id=host.id).tags.get(name="elas_maint").delete()

    if not check_version(api, major=3, minor=2):
        print "This functionality requires api >= 3.2"
        sys.exit(1)

    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster.id)
    else:
        process_cluster(api.clusters.get(name=options.cluster).id)
