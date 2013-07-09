#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for creating cloned machines based on a template
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

# Goals:
# - Do not manage any host without tag elas_manage
# - Operate on one host per execution, exitting after each change
# - Have at least one host up without vm's to hold new VM's
# - Shutdown/suspend hosts without vm's until there's only one left
# - If a host has been put on maintenance and has no tag, it will not be activated by the script
# - Any active host must have no tags on it (that would mean user-enabled, and should have the tag removed)


# tags behaviour
#	 elas_manage: manage this host by using the elastic management script (EMS)
#	 elas_maint : this host has been put on maintenance by the EMS

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
p.add_option("-c", "--cluster", dest="cluster", help="VM cluster", metavar="cluster", default="cluster")
p.add_option("-t", "--template", dest="template", help="VM template", metavar="template", default="template")

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True, persistent_auth=True, session_timeout=3600)

################################ MAIN PROGRAM ############################
#Check if we have defined needed tags and create them if missing
if __name__ == "__main__":
    NEW_VM_NAME = options.name
    CLUSTER_NAME = options.cluster
    TEMPLATE_NAME = options.template

    try:
        api.vms.add(params.VM(name=NEW_VM_NAME, memory=268435456, cluster=api.clusters.get(CLUSTER_NAME), template=api.templates.get(TEMPLATE_NAME)))
        print 'VM was created from Template successfully'

        print 'Waiting for VM to reach Down status'
        while api.vms.get(NEW_VM_NAME).status.state != 'down':
            time.sleep(1)

    except Exception as e:
        print 'Failed to create VM from Template:\n%s' % str(e)
