#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
#
# Description: Script for setting HA
#
# Requires ovirt-engine-sdk to work or RHEVM api equivalent
#
# This software is based on GPL code so:
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
ha is a script for enabling HA for each VM in the cluster
"""

# Option parsing
p = optparse.OptionParser("rhev-ha.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="redhat")
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name", default="name")
p.add_option("--ha", dest="ha", help="High Availability enabled", metavar="ha", default="1", type='int')

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)

try:
    value = api.hosts.list()
except:
    print("Error accessing RHEV-M api, please check data and connection and retry")
    sys.exit(1)

query = ""

for vm in paginate(api.vms, query):
    if vm.high_availability.enabled is not True:
        vm.high_availability.enabled = True
        vm.memory_policy.guaranteed = 1 * 1024 * 1024
        try:
            vm.update()
            print("VM %s updated" % vm.name)
        except:
            print("Failure updating VM HA %s" % vm.name)
