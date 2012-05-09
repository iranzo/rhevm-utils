#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for VM's grouping/ungrouping using ovirt-engine-sdk
# api based on RHCS cluster_ tags on RHEV-M and elas_manage
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

from ovirtsdk.api import API
from ovirtsdk.xml import params
from random import choice

description="""
RHEV-VMs is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's <-> host  rules to avoid having two cluster (RHCS)
nodes at the same physical host.

"""

# Option parsing
p = optparse.OptionParser("rhev-elastic.py [arguments]",description=description)
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
  tags_vm={}
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
  for tag in api.tags.list():
    tags_vm[tag.name]=[]
  
  #Populate the list of tags and VM's
  for vm in api.vms.list():
    if vm.cluster.id==cluster.id:
      if vm.status.state != "down":
        if not vm.tags.get("elas_manage"):
          if options.verbosity > 3:
            print "VM %s is discarded because it has no tag elas_manage" % vm.name
        else:
          vms_in_cluster.append(vm.id)
          for tag in vm.tags.list():
            if options.verbosity > 3:
              print "VM %s in cluster %s has tag %s" % (vm.name,cluster.name,tag.name)
            tags_in_cluster.append(tag.id)
            tags_vm[tag.name].append(vm.name)

  #Construct a list of tags with more than one vm in state != down to process
  for tag in api.tags.list():
    if len(tags_vm[tag.name]) > 1:
      tags_with_more_than_one.append(tag.name)
                
  if options.verbosity > 3:
    print "\nTAGS/VM organization: %s" % tags_vm
    print "TAGS with more than one vm: %s" % tags_with_more_than_one
    
  tags_to_manage=[]
  
  for etiqueta in tags_with_more_than_one:
    if len(tags_vm[etiqueta]) > len(hosts_in_cluster):
      if options.verbosity > 3:
        print "\nMore VM's with tag than available hosts for tag %s, will do as much as I can..." % etiqueta
    else:
      if options.verbosity > 3:
        print "\nContinuing for tag %s"  % etiqueta
    tags_to_manage.append(etiqueta)
      
  if options.verbosity > 3:
    print "Hosts in cluster:"
    print hosts_in_cluster
  
    print "Vm's in cluster"
    print vms_in_cluster
  
    print "Tags in cluster"
    #Removing duplicates
    tags = sorted(set(tags_in_cluster))
    tags_in_cluster = tags
    print tags_in_cluster
      
      
  for etiqueta in tags_to_manage:
    tags_vm_used=set([])
    for vm in tags_vm[etiqueta]:
      if options.verbosity > 4:
        print "Processing vm %s for tag %s at host %s" % (vm,etiqueta,api.hosts.get(id=api.vms.get(name=vm).host.id).name)
      if api.vms.get(name=vm).host.id not in tags_vm_used:
        tags_vm_used.add(api.vms.get(name=vm).host.id)
      else:
        if options.verbosity > 3:
          print "Processing vm %s for tag %s at host %s needs migration" % (vm,etiqueta,api.hosts.get(id=api.vms.get(name=vm).host.id).name)
          for host in hosts_in_cluster:
            target=[]
            if host in tags_vm_used:
              print "Host %s used, skipping" % host
            else:
              print "Host %s not used, migrating there" % host
              target=host

          # Only migrate if VM is up (no down, no migration in progress, etc)
          if api.vms.get(name=vm).status.state="up":
            #Migrate VM to target HOST to satisfy rules
            api.vms.get(name=vm).migrate(params.Action(id=target))

