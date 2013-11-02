#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
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

import sys
import optparse

from ovirtsdk.xml import params
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
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",
             default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("-t", "--table", dest="table", help="Output file in CSV format", metavar='table')

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)


################################ MAIN PROGRAM ############################
try:
    f = open(options.table, 'w')
except:
    print("Problem while opening specified file")
    sys.exit(1)

f.write("TYPE;HOST;STATE;CPU;MEM;VMS;MEMUSED;\n")

#FUNCTIONS
def listvms(oquery=""):
    vms = []
    page = 0
    length = 100
    while length > 0:
        page += 1
        query = "%s page %s" % (oquery, page)
        tanda = api.vms.list(query=query)
        length = len(tanda)
        for vm in tanda:
            vms.append(vm)
    return(vms)


def listhosts(oquery=""):
    hosts = []
    page = 0
    length = 100
    while length > 0:
        page += 1
        query = "%s page %s" % (oquery, page)
        tanda = api.hosts.list(query=query)
        length = len(tanda)
        for host in tanda:
            hosts.append(host)
    return hosts


for host in listhosts():
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

