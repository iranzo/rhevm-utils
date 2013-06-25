#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for exporting a VM by snapshoting, creating a new VM
# based on that snapshot and then exporting the snapshot and deleting the VM
#
# Requires rhevm-sdk to work
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
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
RHEV-clone is a script for creating clones based from a template

"""

# Option parsing
p = optparse.OptionParser("rhev-clone.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name", default="name")

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True)


def snapclone_to_export(api, vmname):
    """Generates a snapshot of a VM, clones it, then exports, and removes the temporary VM"""    

    # GET VM
    name = vmmame

    vm = api.vms.get(name=name)
    cluster=api.clusters.get(id=vm.cluster.id)

    if not vm:
        print "VM %s not found" % vmname
        sys.exit(1)

    # Create new snapshot
    vm.snapshots.add(params.Snapshot(description="Preexport", vm=vm))

    # Wait for snapshot to finish
    while api.vms.get(name=name).status.state == "image_locked":
        sleep(1)

    # Get snapshot object
    snap = api.vms.get(name=name).snapshots.list(description="Preexport")[0]

    # Build snapshots collection
    snapshots = params.Snapshots(snapshot=[params.Snapshot(id=snap.id)])

    # Create new VM from SNAPSHOT (NOT WORKING AT THE MOMENT)
    newname = "%s-deleteme"

    api.vms.add(params.VM(name=newname, snapshots=snapshots, cluster=cluster, template=api.templates.get(name="Blank")))
    # Wait for create to finish
    while api.vms.get(name=newname).status.state == "image_locked":
        sleep(1)

    # DC
    dc = api.datacenters.get(id=cluster.data_center.id)

    # Get Export domain from our DC
    for sd in dc.storagedomains.list():
        if sd.type_ == "export":
            export = sd

    # Export cloned VM to export domain for backup
    api.vms.get(name=newname).export(params.Action(storage_domain=sd))
    # Wait for create to finish
    while api.vms.get(name=newname).status.state == "image_locked":
        sleep(1)

    api.vms.get(name=newname).delete()

    return


################################ MAIN PROGRAM ############################
if __name__ == "__main__":
    NEW_VM_NAME = options.name

    try:
        snapclone_to_export(api, vm=options.name)
        print 'VM was exported succesfully"'

    except Exception as e:
        print 'Failed to export VM'
