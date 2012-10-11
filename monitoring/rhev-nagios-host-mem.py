#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for monitoring host Memory status and VM's rhevm-sdk
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

import sys
import getopt
import optparse
import os
import time

from ovirtsdk.api import API
from ovirtsdk.xml import params
from random import choice

description = """
RHEV-nagios-host-mem output  is a script for querying RHEVM via API to get host status

It's goal is to output a table of host/vm status for simple monitoring via external utilities

"""

# Option parsing
p = optparse.OptionParser("rhev-nagios-host-mem.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="8443", default="8443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option("--host", dest="host", help="Show messages while running", metavar='host')

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True)

################################ MAIN PROGRAM ############################

try:
  host = api.hosts.get(name=options.host)
except:
  print "Host %s not found" % options.host


if not host:
  print "Host %s not found" % options.host
  sys.exit(3)

#NAGIOS PRIOS:
# 0 -> ok
# 1 -> warning
# 2 -> critical
# 3 -> unknown

memory = host.statistics.get(name="memory.used").values.value[0].datum
memtotal = host.statistics.get(name="memory.total").values.value[0].datum

percentage = int(100 * memory / memtotal)

retorno = 3
if percentage >= 90:
  retorno = 1
  if percentage >= 95:
    retorno = 2
else:
  retorno = 0

print percentage
sys.exit(retorno)
