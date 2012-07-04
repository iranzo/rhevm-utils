#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for monitoring host status and VM's ovirt-engine-sdk
# api and produce NAGIOS valid output
#
# Requires ovirt-engine-sdk to work
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
RHEV-nagios-table-host output  is a script for querying RHEVM via API to get host status

It's goal is to output a table of host/vm status for simple monitoring via external utilities

"""

# Option parsing
p = optparse.OptionParser("rhev-nagios-table-host.py [arguments]", description=description)
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option("--host", dest="host", help="Show messages while running", metavar='host')
p.add_option("-t", "--table", dest="table", help="Input file in CSV format", metavar='table')

(options, args) = p.parse_args()

################################ MAIN PROGRAM ############################
if not options.host:
  print "Host not defined, exiting"
  sys.exit(1)

if not options.table:
  print "CSV table not defined, exiting"
  sys.exit(1)

try:
  f = file(options.table)   #fichero a procesar
except:
  print "Problem opening the file %s" % options.table
  sys.exit(1)

#NAGIOS PRIOS:
# 0 -> ok
# 1 -> warning
# 2 -> critical
# 3 -> unknown

# By default, return unknown

#TYPE;HOST;STATE;CPU;MEM
#host;rhev01.lab.local;up;16;0.0


for line in f:
  if line.split(";")[0] == "host":
    if line.split(";")[1] == options.host:
      usage = line.split(";")[2]
      retorno = 3
      if usage == "up":
        retorno = 0
      else:
        retorno = 2
        if usage == "maintenance":
          retorno = 1

      print usage
      sys.exit(retorno)
