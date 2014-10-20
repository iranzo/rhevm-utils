#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for cleaning VM's pinning to hosts using rhevm-sdk
# api based on RHCS cluster_ tags on RHEV-M and elas_manage
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

import optparse

from rhev_functions import *

description = """
RHEV-cleanpinning is a script for managing via API the VMs under RHEV command
in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's <-> host rules to avoid having two cluster
(RHCS) nodes at the same physical host.

"""

# Option parsing
p = optparse.OptionParser("rhev-cleanpinning.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="admin")
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


def process_cluster(clusid):
    """Processes cluster with specified cluster ID
    @param clusid: Cluster ID to process
    """
    query = "cluster = %s" % api.clusters.get(id=clusid).name
    for vm in paginate(api.vms, query):
        if vm.cluster.id == clusid:
            if vm.tags.get("elas_manage"):
                for tag in vm.tags.list():
                    if tag.name[0:8] == "cluster_":
                        if vm.placement_policy.affinity != "migratable":
                            if options.verbosity > 1:
                                print("VM %s pinning removed" % vm.name)
                        vm.placement_policy.affinity = "migratable"
                        vm.placement_policy.host = params.Host()
                        vm.update()
    return


################################ MAIN PROGRAM ############################
if __name__ == "__main__":
    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster.id)
    else:
        process_cluster(api.clusters.get(name=options.cluster).id)
