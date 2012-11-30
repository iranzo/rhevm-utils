#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for creating VLAN in datacenter and attach to cluster and it's hosts
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


import sys
import getopt
import optparse
import os
import time

from ovirtsdk.api import API
from ovirtsdk.xml import params
from rhev_functions import *

description = """
RHEV-vlan is a script for creating via API new VLAN's in RHEV and attach it to DC/Cluster/hosts.

"""

# Option parsing
p = optparse.OptionParser("rhev-vlan.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="8443", default="8443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option('-d', "--datacenter", dest="datacenter", help="datacenter to create the vlan at", metavar='datacenter')
p.add_option('-l', "--vlan", dest="vlan", help="VLAN ID", metavar='vlan')
p.add_option('-n', "--vlanname", dest="vlanname", help="VLANname", metavar='vlanname')
p.add_option('-c', "--cluster", dest="cluster", help="Cluster to attach to", metavar='cluster')
p.add_option('-b', "--bond", dest="bond", help="Bond to create under", metavar='bond', default="bond0")

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True)

if __name__ == "__main__":
    dc = options.datacenter
    vlan = options.vlan

    if not options.vlanname:
        vlanname = "VLAN_%s" % vlan
    else:
        vlanname = options.vlanname

    datacenter = api.datacenters.get(name=dc)
    description = "Network for %s %s" % (vlanname, vlan)
    nueva = params.Network(name=vlanname, data_center=datacenter, vlan=params.VLAN(id=vlan), description=description)
    nueva.vlan_id = int(vlan)

    try:
        red = api.networks.add(nueva)
    except:
        print "ERROR creating VLAN %s with ID %s" % (vlanname, vlan)

    red = api.networks.get(name=vlanname)

    if not red:
        print "Network %s was not found, exitting" % vlanname
        sys.exit(1)

    if red.name != vlanname:
        print "ERROR Found network is not the same as the VLAN we're trying to add!!!!"
        sys.exit(1)

    if options.cluster:
        if options.verbosity > 4:
            print "Attaching network %s to cluster" % red.name
        cluster = api.clusters.get(name=options.cluster)
        try:
            cluster.networks.add(red)
        except:
            if options.verbosity > 4:
                print "Network %s already attached to cluster" % red.name

        query = "cluster = %s" % api.clusters.get(id=cluster.id).name
        for host in listhosts(api, query):
            if host.cluster.id == cluster.id:
                if options.verbosity > 4:
                    print "Host %s is in cluster" % host.name
                accion = params.Action(network=params.Network(name=red.name))
                tarjeta = host.nics.get(name=options.bond)
                try:
                    tarjeta.attach(accion)
                except:
                    if options.verbosity > 4:
                        print "Error attaching network %s to NIC %s" % (red.name, tarjeta.name)

                try:
                    host.commitnetconfig()
                except:
                    if options.verbosity > 4:
                        print "Error commiting network    %s config    to host %s" % (red.name, host.name)
