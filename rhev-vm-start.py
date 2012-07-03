#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for starting VM'susing ovirt-engine-sdk
# api based on single VM dependency
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

# Goals:
# - Do not manage any VM without tag elas_manage
# - reverse missing -> start VM specified
# - reverse 1       -> start all VM's if VM specified is up and running

# tags behaviour
#	 elas_manage: manage this VM by host the elastic management script (EMS)
#        elas_start : make this VM autostart if down


import sys
import getopt
import optparse
import os
import time

from ovirtsdk.api import API
from ovirtsdk.xml import params
from random import choice

description = """
RHEV-vm-start is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's started if another VM is running and host status has not changed

"""

# Option parsing
p = optparse.OptionParser("rhev-vm-cluster.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal", default="admin@internal")
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin", default="admin")
p.add_option("-s", "--server", dest="server", help="RHEV-M server address/hostname to contact", metavar="127.0.0.1", default="127.0.0.1")
p.add_option("-p", "--port", dest="port", help="API port to contact", metavar="8443", default="8443")
p.add_option('-v', "--verbosity", dest="verbosity", help="Show messages while running", metavar='[0-n]', default=0, type='int')
p.add_option('-t', "--tagall", dest="tagall", help="Tag all hosts with elas_manage", metavar='0/1', default=0, type='int')
p.add_option('-c', "--cluster", dest="cluster", help="Select cluster name to process", metavar='cluster', default=None)
p.add_option('-m', "--machine", dest="machine", help="Machine name beggining", metavar="machine", default=None)
p.add_option('-r', "--reverse", dest="reverse", help="Reverse behaviour with machine name", metavar="reverse", default=0)

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password)


#FUNCTIONS
def check_tags():
  if options.verbosity >= 1:
    print "Looking for tags prior to start..."

  if not api.tags.get(name="elas_manage"):
    if options.verbosity >= 2:
      print "Creating tag elas_manage..."
    api.tags.add(params.Tag(name="elas_manage"))

  if not api.tags.get(name="elas_start"):
    if options.verbosity >= 2:
      print "Creating tag elas_start..."
    api.tags.add(params.Tag(name="elas_start"))

  return

def migra(vm, action=None):
  if not action:
    try:
      vm.migrate()
    except:
      if options.verbosity > 4:
        print "Problem migrating auto %s" % vm.name
  else:
    try:
      vm.migrate(action)
    except:
      if options.verbosity > 4:
        print "Problem migrating fixed %s" % vm.name

  loop = True
  counter = 0
  while loop:
    if vm.status.state == "up":
      loop = False
    if options.verbosity > 8:
      print "VM migration loop %s" % counter
    time.sleep(10)
    counter = counter + 1

    if counter > 12:
      loop = False

  return

def process_cluster(cluster):
  # Emtpy vars for further processing
  hosts_in_cluster = []
  vms_in_cluster = []
  tags_in_cluster = []
  tags_vm = {}
  tags_with_more_than_one = []

  # Get host list from this cluster
  for host in api.hosts.list():
    if host.cluster.id == cluster.id:
      hosts_in_cluster.append(host.id)

  if options.verbosity > 2:
    print "\nProcessing cluster %s..." % cluster.name
    print "##############################################"

  #Populate the list of tags and VM's
  for vm in api.vms.list():
    if vm.cluster.id == cluster.id:
      vms_in_cluster.append(vm.id)

  if options.verbosity > 3:
    print "Hosts in cluster:"
    print hosts_in_cluster

    print "Vm's in cluster"
    print vms_in_cluster

  for vm in vms_in_cluster:
    # Iterate until we get our target machine to monitor
    maquina = api.vms.get(id=vm)
    largo = len(options.machine)
    if maquina.name.startswith(options.machine):
      destino = maquina

  # Iterate for all the machines in our cluster and check behaviour based on reverse value
  for vm in vms_in_cluster:
    if options.reverse == 0:
      if destino.status.state == "down":
        if options.verbosity > 3:
          print "Our VM is down... try to start it if possible"
        one_is_up = False
        for host in hosts_in_cluster:
          if api.hosts.get(id=host).status.state == "up":
            one_is_up = True
        if one_is_up:
          try:
            destino.start()
          except:
            if options.verbosity > 3:
              print "Error starting up machine %s" % destino.name
    else:
      # Reverse is != 0... then just boot if target machine is already up
      if destino.status.state == "up":
        # Our target VM is not down, it's safe to start our machines up!
        for vm in vms_in_cluster:
          maquina = api.vms.get(id=vm)
          if maquina.status.state != "up":
            if maquina.id != destino.id:
              try:
                maquina.start()
              except:
                if options.verbosity > 3:
                  print "Error starting %s" % maquina.name
      else:
        if options.verbosity > 3:
          print "Target machine is not up, not starting vm"

################################ MAIN PROGRAM ############################

if options.machine == "":
  print "Error machine name must be defined"
  sys.exit(1)

if not options.cluster:
  # Processing each cluster of our RHEVM
  for cluster in api.clusters.list():
    process_cluster(cluster)
else:
  process_cluster(api.clusters.get(name=options.cluster))
