#!/usr/bin/env python
#
# Author:    Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
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

import optparse

import psycopg2

from rhev_functions import *


description = """
rhev-vm-applist is a script for gathering statistics about VM usage that can be used to tax usage
"""

# Option parsing
p = optparse.OptionParser("rhev-vm-applist.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="redhat")
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="server",
             default="127.0.0.1")
p.add_option("--dbuser", dest="dbuser", help="RHEV-M database user", metavar="dbuser", default="engine")
p.add_option("--dbpass", dest="dbpass", help="RHEV-M database password", metavar="dbpass", default="redhat")

p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name")

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)
con = psycopg2.connect(database='engine', user=options.dbuser, password=options.dbpass)

try:
    value = api.vms.list()
except:
    print("Error accessing RHEV-M api, please check data and connection and retry")
    sys.exit(1)


# FUNCTIONS
def gathervmdata(vmname):
    """Obtans VM data from Postgres database and RHEV api
    @param vmname: VM name to get information for
    """
    # Get VM ID for the query
    vmid = api.vms.get(name=vmname).id

    # sql Query for gathering date from range
    sql = "select app_list as vm_apps from vm_dynamic where vm_guid='%s' ;" % vmid

    cur.execute(sql)
    rows = cur.fetchall()

    return rows[0]


def vmdata(vm):
    """Returns a list of VM data
    @param vm: object identifying VM and return information from it
    """
    # VMNAME, VMRAM, VMRAMAVG, VMCPU, VMCPUAVG, VMSTORAGE, VMSIZE
    vmdata = [vm.name, gathervmdata(vm.name)]
    return vmdata


def htmlrow(lista):
    """Returns an HTML row for a table
    @param lista: Elements to put as diferent columns to construct a row
    """
    table = "<tr>"
    for elem in lista:
        table += "<td>%s</td>" % elem
    table += "</tr>"
    return table


def htmltable(listoflists):
    """Returns an HTML table based on Rows
    @param listoflists: Contains a list of all table rows to generate a table
    """
    table = "<table>"
    for elem in listoflists:
        table += htmlrow(elem)
    table += "</table>"
    return table

# MAIN PROGRAM
if __name__ == "__main__":

    # Open connection
    cur = con.cursor()

    print("<html>")
    print("<head><title>VM Table</title></head><body>")

    if not options.name:
        data = [["Name", "App list"]]
        for vm in paginate(api.vms):
            try:
                data.append(vmdata(vm))
            except:
                skip = 1
    else:
        data = [["VMNAME", "APP list"], vmdata(api.vms.get(name=options.name))]

    print(htmltable(data))

    if con:
        con.close()

    print("</body></html>")
