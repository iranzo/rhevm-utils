#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
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

# Contributors:
# Ian Lochrin LOCHRINI at stgeorge.com.au
# Denis Immoos at dimmoos@scope.ch


import optparse

from rhev_functions import *

description = """
RHEV-vm-clone-to-export is a script for creating clones based from a vm snapshot

"""

# Option parsing
p = optparse.OptionParser("rhev-vm-clone-to-export.py [arguments]", description=description)
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
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=1,
             type='int')

# Denis Immoos at dimmoos@scope.ch
p.add_option('-q', "--quiet", dest="verbosity", help="quiet while running", action="store_false")
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name", default="name")
p.add_option("-r", "--reboot", dest="reboot", help="should we reboot", action="store_true")
p.add_option("-x", "--shutdown", dest="shutdown", help="should we shutdown", action="store_true")

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)

sleep_time = 10
date_string = time.strftime('%Y%m%d%H%M', time.localtime())


def snapclone_to_export(api, vm):

    """Generates a snapshot of a VM, clones it, then exports, and removes the temporary VM
    @param api: pass API call to this function
    @param vm: VM to process
    """

    # Denis Immoos at dimmoos@scope.ch
    # description = "Preexport-%s" % time.mktime(time.gtmtime())
    description = "Preexport-%s" % date_string

    # GET VM
    cluster = api.clusters.get(id=vm.cluster.id)

    if not vm:
        print("vm %s not found" % vm.name)
        sys.exit(1)

    # Denis Immoos at dimmoos@scope.ch
    if options.reboot or options.shutdown:
        if options.verbosity > 0:
            print("stopping " + vm.name + " ...")
        if api.vms.get(name=vm.name).status.state != 'down':
            api.vms.get(name=vm.name).shutdown()
            while api.vms.get(name=vm.name).status.state != 'down':
                if options.verbosity > 0:
                    print "waiting for " + vm.name + " to reach down status ..."
                time.sleep(sleep_time)
            if options.verbosity > 0:
                print vm.name + " is down ..."
        else:
            if options.verbosity > 0:
                print vm.name + " is allready down ..."

        # sleep a bit
        # time.sleep(sleep_time)

    # END Denis Immoos at dimmoos@scope.ch

    # Create new snapshot
    if options.verbosity > 0:
        print("creating snapshot " + description + " ...")

    vm.snapshots.add(params.Snapshot(description=description, vm=vm))

    # Wait for snapshot to finish
    while api.vms.get(name=vm.name).status.state == "image_locked":
        if options.verbosity > 0:
            print("waiting for snapshot " + description + " to finish ...")
        time.sleep(sleep_time)

    # Get snapshot object
    snap = api.vms.get(name=vm.name).snapshots.list(description=description)[0]

    # Build snapshots collection
    snapshots = params.Snapshots(snapshot=[params.Snapshot(id=snap.id)])

    while api.vms.get(name=vm.name).snapshots.get(id=snap.id).snapshot_status != "ok":
        if options.verbosity > 0:
            print("waiting for snapshot " + description + " to finish ...")
        time.sleep(sleep_time)

    # Create new VM from SNAPSHOT (NOT WORKING AT THE MOMENT)
    # newname = "%s-deleteme" % vm.name
    newname = vm.name
    newname += "-"
    newname += date_string

    if options.verbosity > 0:
        print("creating new vm " + newname + " based on snapshot " + description + " ...")

    api.vms.add(params.VM(name=newname, snapshots=snapshots, cluster=cluster, template=api.templates.get(name="Blank")))

    # Wait for create to finish
    while api.vms.get(name=newname).status.state == "image_locked":
        if options.verbosity > 0:
            print("waiting for " + newname + " to finish ...")
        time.sleep(sleep_time)

    # DC
    dc = api.datacenters.get(id=cluster.data_center.id)

    # Get Export domain from our DC
    export = None

    for sd in dc.storagedomains.list():
        if sd.type_ == "export":
            export = sd

    if not export:
        print("ERROR: export domain required, and none found, exitting ...")
        sys.exit(1)

    if options.verbosity > 0:
        print("exporting " + newname + " to " + export.name + " ...")

    # Export cloned VM to export domain for backup
    api.vms.get(name=newname).export(params.Action(storage_domain=export, exclusive=True))

    # Wait for create to finish
    while api.vms.get(name=newname).status.state == "image_locked":
        if options.verbosity > 0:
            print("waiting for export to finish ...")
        time.sleep(sleep_time)

    if options.verbosity > 0:
        print("deleting temporary vm " + newname + " ...")
    api.vms.get(name=newname).delete()

    if api.vms.get(name=vm.name).status.state != 'up':

        if options.verbosity > 0:
            print("deleting temporary snapshot ...")

        snapshotlist = api.vms.get(name=vm.name).snapshots.list()
        for snapshot in snapshotlist:
            if "Preexport-" in snapshot.description:
                snapshot.delete()
                try:
                    while api.vms.get(name=vm.name).snapshots.get(id=snapshot.id).snapshot_status == "locked":
                        if options.verbosity > 0:
                            print "waiting for snapshot %s on %s deletion to finish ..." % (snapshot.description, vm.name)
                        time.sleep(sleep_time)
                except Exception as e:
                    if options.verbosity > 0:
                        print "snapshot %s does not exist anymore ..." % snapshot.description

        print "snapshot deletion for %s done" % vm.name

    # Denis Immoos at dimmoos@scope.ch
    if options.reboot:
        print("starting " + vm.name + " ...")
        if api.vms.get(name=vm.name).status.state != 'up':
            api.vms.get(name=vm.name).start()
            while api.vms.get(name=vm.name).status.state != 'up':
                if options.verbosity > 0:
                    print "waiting for " + vm.name + " to reach up status ..."
                time.sleep(sleep_time)
            print vm.name + " is up ..."
        else:
            if options.verbosity > 0:
                print vm.name + " is allready up ..."
    # END Denis Immoos at dimmoos@scope.ch

    return

# MAIN PROGRAM
#
# Uncomment for debug the exception creation
#
# snapclone_to_export(api, vm=api.vms.get(name=options.name))
# sys.exit(0)

if __name__ == "__main__":
    NEW_VM_NAME = options.name
    if not options.name:
        print("vm name is required ...")
        sys.exit(1)

    if not check_version(api, major=3, minor=2):
        print("This functionality requires api >= 3.2")
        sys.exit(1)

    try:
        snapclone_to_export(api, vm=api.vms.get(name=options.name))
        print('vm was exported succesfully ...')

    except Exception as e:
        print('ERROR: failed to export vm')
