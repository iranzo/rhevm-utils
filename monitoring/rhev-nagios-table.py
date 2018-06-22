#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
#
# Description: Script for monitoring host and storage status and ouptut in a
# CSV table for later parsing using VM's rhevm-sdk.  Then, another
# subset of scripts will query that table instead of querying RHEV-M api to
# reduce the number of API calls
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
RHEV-nagios-table is a script for querying RHEV-M status and put in on a table for later querying

It's goal is to output a table of host/vm status for simple monitoring via external utilities

"""

# Option parsing
p = optparse.OptionParser("rhev-nagios-table.py [arguments]", description=description)
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
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("-t", "--table", dest="table", help="Output file in CSV format", metavar='table')

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


# MAIN PROGRAM
try:
    f = open(options.table, 'w')
except:
    print("Problem while opening specified file")
    sys.exit(1)

f.write("TYPE;HOST;STATE;CPU;MEM;VMS;MEMUSED;\n")

# FUNCTIONS
for host in paginate(api.hosts):
    memory = host.statistics.get(name="memory.used").values.value[0].datum
    memtotal = host.statistics.get(name="memory.total").values.value[0].datum
    usage = (100 - host.statistics.get(name="cpu.current.idle").values.value[0].datum)
    percentage = int(100 * memory / memtotal)
    vms = host.summary.total

    # Patch exit status based on elas_maint
    if host.status.state != "up":
        status = "unknown"
        if host.tags.get("elas_maint"):
            status = "up"
        if host.status.state == "maintenance":
            status = "maintenance"
    else:
        status = host.status.state

    fullstatus = "host;%s;%s;%s;%s;%s;%s;\n" % (host.name, status, percentage, usage, vms, memory)
    f.write(fullstatus)

f.write("TYPE;SD;PCTG\n")
for sd in api.storagedomains.list():
    try:
        memory = sd.used
    except:
        memory = 0
    try:
        memtotal = sd.available
    except:
        memtotal = 0

    try:
        percentage = int(100 * memory / memtotal)
    except:
        percentage = 0

    fullstatus = "SD;%s;%s;\n" % (sd.name, percentage)
    f.write(fullstatus)

f.close()
sys.exit(0)
