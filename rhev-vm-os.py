#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for VM's grouping/ungrouping using ovirt-engine-sdk
# api based on O.S. and Host load
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
# - Do not run vm's from a named cluster run on the same host (cluster_)
# - Do not manage any VM without tag elas_manage

# tags behaviour
#	 elas_manage: manage this VM by using the elastic management script (EMS)
#        cluster_***: make this VM part of a RHCS 'cluster' to avoid same-host placement
#


import sys
import getopt
import optparse
import os
import time
import operator

from ovirtsdk.api import API
from ovirtsdk.xml import params
from random import choice


description="""
RHEV-vm-os is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's <-> host <-> O.S.  to group VM's using same O.S. to take benefit of KSM within nodes at the same physical host.

"""

# Option parsing
p = optparse.OptionParser("rhev-vm-os.py [arguments]",description=description)
p.add_option("-u", "--user", dest="username",help="Username to connect to RHEVM API", metavar="admin@internal",default="admin@internal")
p.add_option("-w", "--password", dest="password",help="Password to use with username", metavar="admin",default="admin")
p.add_option("-s", "--server", dest="server",help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",default="127.0.0.1")
p.add_option("-p", "--port", dest="port",help="API port to contact", metavar="8443",default="8443")
p.add_option('-v', "--verbosity", dest="verbosity",help="Show messages while running", metavar='[0-n]', default=0,type='int')
p.add_option('-t', "--tagall", dest="tagall",help="Tag all hosts with elas_manage", metavar='0/1', default=0,type='int')

(options, args) = p.parse_args()

baseurl="https://%s:%s" % (options.server,options.port)

api = API(url=baseurl, username=options.username, password=options.password)

#FUNCTIONS
def check_tags():
  if options.verbosity >= 1:
    print "Looking for tags elas_manage prior to start..."

  if not api.tags.get(name="elas_manage"):
    if options.verbosity >=2:
      print "Creating tag elas_manage..."    
    api.tags.add(params.Tag(name="elas_manage"))

  return  
  
################################ MAIN PROGRAM ############################
#Check if we have defined needed tags and create them if missing
check_tags()

# TAGALL?
#Add elas_maint TAG to every single vm to automate the management
if options.tagall == 1:
  if options.verbosity >=1:
    print "Tagging all VM's with elas_manage"
  for vm in api.vms.list():
    try:
      vm.tags.add(params.Tag(name="elas_manage"))
    except:
      print "Error adding elas_manage tag to vm %s" % vm.name
      
      
for cluster in api.clusters.list():
  # Emtpy vars for further processing
  hosts_in_cluster= []
  vms_in_cluster=[]
  tags_in_cluster=[]
  tags_os={}
  tags_with_more_than_one=[]
  
  # Get host list from this cluster
  for host in api.hosts.list():
    if host.cluster.id==cluster.id:
      if host.status.state == "up":
        hosts_in_cluster.append(host.id)
        
  if options.verbosity > 2:
    print "\nProcesando cluster %s..." % cluster.name
    print "##############################################"
  
  #Create the empty set of vars that we'll populate later
  for vm in api.vms.list():
    tags_os[vm.os.type_]=[]
  
  #Populate the list of tags and VM's
  for vm in api.vms.list():
    if vm.cluster.id==cluster.id:
      if vm.status.state == "up":
        if not vm.tags.get("elas_manage"):
          if options.verbosity > 3:
            print "VM %s is discarded because it has no tag elas_manage" % vm.name
        else:
          # Add the VM Id to the list of VMS to manage in this cluster
          vms_in_cluster.append(vm.id)
          for tag in vm.tags.list():
            tags_os[vm.os.type_].append(vm.name)

          
  # Sort the tags by the number of elements in it
  sorted_tags_os=sorted(tags_os.iteritems(), key=lambda x:x[1], reverse=True)

  # Print tags/vm's distribution  
  if options.verbosity > 3:  
    print "OS/VM's"
    print tags_os
    print "Hosts in cluster"
    print hosts_in_cluster
  
  # VM's to process:
  vms_to_process=[]

  for vm in api.vms.list():
    if vm.cluster.id == cluster.id:
      vms_to_process.append(vm.name)

  if options.verbosity > 3:
    print "VM's to process"
    print vms_to_process

  # Move away from initial host all the vm's not part of bigger set
  for vm in api.vms.list():
    # VM is UP
    if vm.status.state == "up":
      # VM is running at actual host
      if len(hosts_in_cluster) != 0:
        if vm.host.id==hosts_in_cluster[0]:
          # VM os type is not the primary one
          if vm.os.type_ != sorted_tags_os[0][0]:
            # VM is not of primary type... move it away!!
              if options.verbosity > 3:
                print "Probando a migrar %s" % vm.name
              try:
                vm.migrate()
              except:
                failed=0
          else:
            vms_to_process.remove(vm.name)

  if options.verbosity > 3:       
    print "VM's remaining"
    print vms_to_process

  i = 0
  while i < len(tags_os):
    #Sort the tags
    etiqueta=sorted_tags_os[i][0]
    i=i+1
    if options.verbosity > 1:
      print "Processing tag %s" % etiqueta

    # start with bigger set of tag
    for host in hosts_in_cluster:
      free_ram=api.hosts.get(id=host).statistics.get("memory.free").values.value[0].datum
      for vm in vms_to_process:
        if api.vms.get(name=vm).os.type_ == etiqueta:
          maquina=api.vms.get(name=vm)
          if maquina.status.state=="up":
            if maquina.host.id != host:
              if free_ram > maquina.statistics.get("memory.used").values.value[0].datum:
                # We've free space, move in there...
                if options.verbosity > 2:
                  print "Enough memory on %s to migrate %s" % (api.hosts.get(id=host).name,maquina.name)
                maquina.migrate(params.Action(host=api.hosts.get(id=host)))
                free_ram = free_ram - maquina.statistics.get("memory.used").values.value[0].datum
              else:
                if options.verbosity > 2:              
                  print "Not enough ram, hopping to next host"
                break
