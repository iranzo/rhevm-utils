#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for switching clusters policy to specified one, actually power_saving or evenly_distributed
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
RHEV-policy is a script for managing via API cluster policy

Actual policy is:
- power_saving
- evenly_distributed

"""

# Option parsing
p = optparse.OptionParser("rhev-policy.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option("--policy", dest="policy", help="Set destination policy", metavar='policy', default="power_saving")
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)


(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True, persistent_auth=True, session_timeout=3600)


# FUNCTIONS
def process_cluster(clusid):
    """Processes cluster"""
    if options.verbosity > 1:
        print "\nProcessing cluster with id %s and name %s" % (clusid, api.clusters.get(id=clusid).name)
        print "#############################################################################"

    cluster = api.clusters.get(id=clusid)
    cluster.scheduling_policy.policy = options.policy
    try:
        cluster.update()
    except:
        if options.verbosity > 2:
            print "Problem updating policy"

    #evenly_distributed
    #power_saving


################################ MAIN PROGRAM ############################
if __name__ == "__main__":

    if not options.cluster:
        # Processing each cluster of our RHEVM
        for cluster in api.clusters.list():
            process_cluster(cluster.id)
    else:
        process_cluster(api.clusters.get(name=options.cluster).id)
