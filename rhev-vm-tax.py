#!/usr/bin/env python
#
# Author:            Pablo Iranzo Gomez (Pablo.Iranzo@gmail.com)
# Description: Script for accessing RHEV-M history DB for gathering historical usage data for current month and VM
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

import calendar
import datetime
import optparse

import psycopg2

from rhev_functions import *

description = """
rhev-vm-tax is a script for gathering statistics about VM usage that can be used to tax usage
"""

# Option parsing
p = optparse.OptionParser("rhev-vm-tax.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default="redhat")
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option("-k", action="store_true", dest="keyring", help="use python keyring for user/password", metavar="keyring",
             default=False)
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="server",
             default="127.0.0.1")
p.add_option("--dbname", dest="dbname", help="RHEV-M database name", metavar="dbname", default="engine")
p.add_option("--dbuser", dest="dbuser", help="RHEV-M database user", metavar="dbuser", default="engine")
p.add_option("--dbpass", dest="dbpass", help="RHEV-M database password", metavar="dbpass", default="redhat")
p.add_option("-D", action="store_true", dest="dbaskpassword", help="Ask for DB password", metavar="admin",
             default=False)
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="443", default="443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0,
             type='int')
p.add_option("-n", "--name", dest="name", help="VM name", metavar="name")
p.add_option("-d", "--startday", dest="startday", help="Starting day of period", metavar="startday", default="1")
p.add_option("-e", "--endday", dest="endday", help="Ending day of period, defaults to end of month", metavar="endday")
p.add_option("-m", "--month", dest="month", help="Month to gather data from", metavar="month", type='int')
p.add_option("-y", "--year", dest="year", help="Year to gather data from", metavar="year", type='int')

(options, args) = p.parse_args()

options.username, options.password = getuserpass(options)


# TODO: Create keyring for DBpassword
if options.dbaskpassword:
    options.dbpass = getpass.getpass("Enter DB password: ")

baseurl = "https://%s:%s/ovirt-engine/api" % (options.server, options.port)

api = apilogin(url=baseurl, username=options.username, password=options.password)
con = psycopg2.connect(database=options.dbname, user=options.dbuser, password=options.dbpass)

try:
    value = api.vms.list()
except:
    print("Error accessing RHEV-M api, please check data and connection and retry")
    sys.exit(1)


# FUNCTIONS
def gathervmdata(vmname):
    """Obtans VM data from Postgres database and RHEV api
    @param vmname: VM name to gather data for
    """
    # Get VM ID for the query
    vmid = api.vms.get(name=vmname).id

    # SQL Query for gathering date from range
    sql = "select history_datetime as DateTime, cpu_usage_percent as CPU, memory_usage_percent as Memory from " \
          "vm_daily_history where vm_id='%s' and history_datetime >= '%s' and history_datetime <= '%s' ;" % (
              vmid, datestart, dateend)

    cur.execute(sql)
    rows = cur.fetchall()

    totcpu = 0
    totmemory = 0
    totsample = len(rows)

    if totsample == 0:
        return 0, 0
    else:
        for row in rows:
            cpu = "%f" % float(row[1])
            memory = "%f" % float(row[2])
            totcpu = float(totcpu) + float(cpu)
            totmemory = float(totmemory) + float(memory)

        cpuavg = "%.4f" % float(totcpu / totsample)
        ramavg = "%.4f" % float(totmemory / totsample)

        return cpuavg, ramavg


def vmdata(vm):
    """Returns a list of VM data
    @param vm: VM api object for a specified VM
    """
    # VMNAME, VMRAM, VMRAMAVG, VMCPU, VMCPUAVG, VMSTORAGE, VMSIZE, HOST
    vmdata = [vm.name, vm.memory / 1024 / 1024 / 1024]
    vmcpuavg, vmramavg = gathervmdata(vm.name)
    vmdata.append(vmramavg)
    vmdata.append(vm.cpu.topology.cores)
    vmdata.append(vmcpuavg)
    storage = api.storagedomains.get(id=vm.disks.list()[0].storage_domains.storage_domain[0].id).name
    vmdata.append(storage)
    tamanyo = 0
    for disk in vm.disks.list():
        tamanyo += disk.size / 1024 / 1024 / 1024
    vmdata.append(tamanyo)
    try:
        host = api.hosts.get(id=vm.host.id).name
    except:
        host = None
    vmdata.append(host)

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

    # Obtain current date
    now = datetime.datetime.now()

    # Calculate year
    if not options.year:
        year = now.year
    else:
        year = options.year

    # Calculate month
    if not options.month:
        if now.month > 1:
            month = now.month - 1
        else:
            month = 12
            year -= 1
    else:
        month = options.month

    # Calculate month's end day
    if options.endday:
        endday = options.endday
    else:
        endday = calendar.monthrange(year, month)[1]

    startday = options.startday

    # Construct dates for SQL query
    datestart = "%s-%s-%s 00:00" % (year, month, startday)
    dateend = "%s-%s-%s 23:59" % (year, month, endday)

    # Open connection
    cur = con.cursor()

    print("<html>")
    print("<head><title>VM Table</title></head><body>")

    if not options.name:
        data = [
            ["Name", "RAM (GB)", "% RAM used", "Cores", "%CPU used", "Storage Domain", "Total assigned (GB)", "HOST"]]
        for vm in paginate(api.vms):
            try:
                data.append(vmdata(vm))
            except:
                skip = 1
    else:
        data = [["VMNAME", "VMRAM", "VM RAM AVG", "VM CPU", "VM CPU AVG", "VM Storage", "HDD SIZE", "HOST"],
                vmdata(api.vms.get(name=options.name))]

    print(htmltable(data))

    if con:
        con.close()

    print("</body></html>")
