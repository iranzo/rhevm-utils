#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
#
# Description: Script for monitoring host status and VM's rhevm-sdk
# api and produce NAGIOS valid output
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

import optparse

from rhev_functions import *

description = """
RHEV-nagios-storage output  is a script for querying RHEVM via API to get host status

It's goal is to output a table of host/vm status for simple monitoring via external utilities

"""

# Option parsing
p = optparse.OptionParser("rhev-nagios-host.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="admin")
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("--storage", dest="storage", help="Show messages while running", metavar='storage')

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


# MAIN PROGRAM

# if not options.host:

try:
    sd = api.storagedomains.get(name=options.storage)
except:
    print("Storage Domain %s not found" % options.storage)

if not sd:
    print("Storage Domain %s not found" % options.storage)
    sys.exit(3)

# NAGIOS PRIOS:
# 0 -> ok
# 1 -> warning
# 2 -> critical
# 3 -> unknown

memory = sd.used
memtotal = sd.available

percentage = int(100 * memory / memtotal)

retorno = 3
if percentage >= 90:
    retorno = 1
    if percentage >= 95:
        retorno = 2
else:
    retorno = 0

print(percentage)
sys.exit(retorno)
