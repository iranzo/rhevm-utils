#!/usr/bin/env python
#
# Author:    Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
# Description: Script for accessing RHEV-M DB for gathering app list for a given VM
#
# Requires rhevm-sdk to work and psycopg2 (for PG access)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.

import psycopg2
import sys
import getopt
import optparse
import os
import time
import calendar
import datetime

from ovirtsdk.api import API
from ovirtsdk.xml import params
from rhev_functions import *

description = """
rhev-vm-applist is a script for gathering statistics about VM usage that can be used to tax usage
"""

# Option parsing
p = optparse.OptionParser("rhev-vm-applist.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="redhat")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="server", default="127.0.0.1")
p.add_option("--dbuser", dest="dbuser", help="RHEV-M database user", metavar="dbuser", default="engine")
p.add_option("--dbpass", dest="dbpass", help="RHEV-M database password", metavar="dbpass", default="redhat")

p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name")


(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True, persistent_auth=True, session_timeout=3600)
con = psycopg2.connect(database='engine', user=options.dbuser, password=options.dbpass)

try:
    value = api.vms.list()
except:
    print "Error accessing RHEV-M api, please check data and connection and retry"
    sys.exit(1)


################################ FUNCTIONS        ############################
def gatherVMdata(vmname):
    """Obtans VM data from Postgres database and RHEV api"""
    # Get VM ID for the query
    vmid = api.vms.get(name=vmname).id

    # SQL Query for gathering date from range
    SQL = "select app_list as vm_apps from vm_dynamic where vm_guid='%s' ;" % vmid

    cur.execute(SQL)
    rows = cur.fetchall()

    return rows[0]


def VMdata(vm):
    """Returns a list of VM data"""
    # VMNAME, VMRAM, VMRAMAVG, VMCPU, VMCPUAVG, VMSTORAGE, VMSIZE
    vmdata = []
    vmdata.append(vm.name)
    vmdata.append(gatherVMdata(vm.name))
    return vmdata


def HTMLRow(list):
    """Returns an HTML row for a table"""
    table = "<tr>"
    for elem in list:
        table = table + "<td>%s</td>" % elem
    table = table + "</tr>"
    return table


def HTMLTable(listoflists):
    """Returns an HTML table based on Rows"""
    table = "<table>"
    for elem in listoflists:
        table = table + HTMLRow(elem)
    table = table + "</table>"
    return table

################################ MAIN PROGRAM ############################
if __name__ == "__main__":

    # Open connection
    cur = con.cursor()

    print "<html>"
    print "<head><title>VM Table</title></head><body>"

    if not options.name:
        data = []
        data.append(["Name", "App list"])
        for vm in listvms(api):
            try:
                data.append(VMdata(vm))
            except:
                skip = 1
    else:
        data = []
        data.append(["VMNAME", "APP list"])
        data.append(VMdata(api.vms.get(name=options.name)))

    print HTMLTable(data)

    if con:
        con.close()

    print "</body></html>"
