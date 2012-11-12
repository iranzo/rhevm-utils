#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for VM's grouping/ungrouping using rhevm-sdk
# api based on RHCS cluster_ tags on RHEV-M and elas_manage
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

# Goals:
# - Do not run vm's from a named cluster run on the same host (cluster_)
# - Do not manage any VM without tag elas_manage

# tags behaviour
#	 elas_manage: manage this VM by using the elastic management script (EMS)
#        elas_start : make this VM autostart if down
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

description = """
RHEV-vm-cluster is a script for managing via API the VMs under RHEV command in both RHEV-H and RHEL hosts.

It's goal is to keep some VM's <-> host  rules to avoid having two cluster (RHCS)
nodes at the same physical host.

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

(options, args) = p.parse_args()

baseurl = "https://%s:%s" % (options.server, options.port)

api = API(url=baseurl, username=options.username, password=options.password, insecure=True)




#FUNCTIONS
def listvms(oquery=""):
  """Returns a list of VM's based on query"""
  vms = []
  page = 0
  length = 100
  while (length > 0):
    page = page + 1
    query = "%s page %s" % (oquery, page)
    tanda = api.vms.list(query=query)
    length = len(tanda)
    for vm in tanda:
      vms.append(vm)
  return(vms)
  
def listhosts(oquery=""):
  """Returns a list of Hosts based on query"""
  hosts = []
  page = 0
  length = 100
  while (length > 0):
    page = page + 1
    query = "%s page %s" % (oquery, page)
    tanda = api.hosts.list(query=query)
    length = len(tanda)
    for host in tanda:
      hosts.append(host)
  return(hosts)  

def check_tags():
  """Checks if required tags have been already defined"""
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
  """Migrates a VM to a specified target host or automatically if none"""
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
  """Processes cluster"""
  # Emtpy vars for further processing
  hosts_in_cluster = []
  vms_in_cluster = []
  tags_in_cluster = []
  tags_vm = {}
  tags_with_more_than_one = []
  
  # Get host list from this cluster
  query = "cluster = %s and status = up" % api.clusters.get(id=cluster.id).name
  for host in listhosts(query):
    if host.cluster.id == cluster.id:
      if host.status.state == "up":
        hosts_in_cluster.append(host.id)
        
  if options.verbosity > 2:
    print "\nProcessing cluster %s..." % cluster.name
    print "##############################################"
  
  #Create the empty set of vars that we'll populate later
  for tag in api.tags.list():
    tags_vm[tag.name] = []
  
  #Populate the list of tags and VM's
  query = "cluster = %s and status = up and tag = elas_manage" % api.clusters.get(id=cluster.id).name
  for vm in listvms(query):
    if vm.cluster.id == cluster.id:
      if vm.status.state == "up":
        if not vm.tags.get("elas_manage"):
          if options.verbosity > 3:
            print "VM %s is discarded because it has no tag elas_manage" % vm.name
        else:
          # Add the VM Id to the list of VMS to manage in this cluster
          vms_in_cluster.append(vm.id)
          for tag in vm.tags.list():
            if tag.name[0:8] == "cluster_":
              if options.verbosity > 3:
                print "VM %s in cluster %s has tag %s" % (vm.name, cluster.name, tag.name)
              # Put the TAG in the list of used for this cluster and put the VM to the ones with this tag
              tags_in_cluster.append(tag.id)
              tags_vm[tag.name].append(vm.name)

  #Construct a list of tags with more than one vm in state == up to process
  for tag in api.tags.list():
    if len(tags_vm[tag.name]) > 1:
      if tag.name[0:8] == "cluster_":
        tags_with_more_than_one.append(tag.name)
                
  if options.verbosity > 3:
    print "\nTAGS/VM organization: %s" % tags_vm
    print "TAGS with more than one vm: %s" % tags_with_more_than_one
    
  tags_to_manage = []
  
  for etiqueta in tags_with_more_than_one:
    if len(tags_vm[etiqueta]) > len(hosts_in_cluster):
      if options.verbosity > 3:
        print "\nMore VM's with tag than available hosts for tag %s, will do as much as I can..." % etiqueta
    else:
      if options.verbosity > 3:
        print "\nContinuing for tag %s" % etiqueta
    if etiqueta[0:8] == "cluster_":
      tags_to_manage.append(etiqueta)
    
  #Removing duplicates
  tags = sorted(set(tags_in_cluster))
  tags_in_cluster = tags    
      
  if options.verbosity > 3:
    print "Hosts in cluster:"
    print hosts_in_cluster
  
    print "Vm's in cluster"
    print vms_in_cluster
  
    print "Tags in cluster"
    print tags_in_cluster
      
      
  for etiqueta in tags_to_manage:
    tags_vm_used = set([])
    if options.verbosity > 3:
      print "Managing tag %s" % etiqueta
    for vm in tags_vm[etiqueta]:
      if options.verbosity > 4:
        print "Processing vm %s for tag %s at host %s" % (vm, etiqueta, api.hosts.get(id=api.vms.get(name=vm).host.id).name)

      #Set target as actual running host
      target = api.vms.get(name=vm).host.id

      if api.vms.get(name=vm).host.id not in tags_vm_used:
        #Host not yet used, accept it directly
        tags_vm_used.add(target)
      else:
        # Host was in use, searching for new target
        for host in hosts_in_cluster:
          if host in tags_vm_used:
            if options.verbosity > 4:
              print "Host %s used, skipping" % host
          else:
            if options.verbosity > 4:
              print "Host %s not used, migrating there" % host
            # Setting new host
            target = host

        
      nombre = api.hosts.get(id=target).name
      

      # Only migrate if VM if there's host change
      maquina = api.vms.get(name=vm)
      
      if maquina.host.id != target:
        if options.verbosity > 3:
          print "Processing vm %s for tag %s at host %s needs migration to host %s" % (vm, etiqueta, api.hosts.get(id=api.vms.get(name=vm).host.id).name, nombre)
        # Allow migration
        maquina.placement_policy.host = params.Host()
        maquina.placement_policy.affinity = "migratable"
        maquina.update()
            
        #Migrate VM to target HOST to satisfy rules
        migra(api.vms.get(name=vm), params.Action(host=api.hosts.get(id=target)))
        tags_vm_used.add(target)        
      else:
        if options.verbosity > 4:
          print "Skipping migration target=host"

      # Discard further migration of any machine
      maquina.placement_policy.affinity = "pinned"
      maquina.placement_policy.host = api.hosts.get(id=target)
      try:
        maquina.update()
      except:
        if options.verbosity > 4:
          print "Problem updating VM parameters for pinning"


  
################################ MAIN PROGRAM ############################
#Check if we have defined needed tags and create them if missing
check_tags()

# TAGALL?
#Add elas_maint TAG to every single vm to automate the management
if options.tagall == 1:
  if options.verbosity >= 1:
    print "Tagging all VM's with elas_manage"
  for vm in listvms():
    try:
      vm.tags.add(params.Tag(name="elas_manage"))
    except:
      print "Error adding elas_manage tag to vm %s" % vm.name
      
      
# CLEANUP
# Remove pinning from vm's in down state to allow to start in any host
query = "status = down"
for vm in listvms(query):
  if vm.status.state == "down":
      if vm.tags.get("elas_manage"):
        for tag in vm.tags.list():
          if tag.name[0:8] == "cluster_":
            if options.verbosity >= 5:
              print "Cleaning VM %s pinning to allow to start on any host" % vm.name
            # If powered down, allow machine to be migratable so it can start on any host
            maquina = vm
            maquina.placement_policy.host = params.Host()
            maquina.placement_policy.affinity = "migratable"
            maquina.update()
      if vm.tags.get("elas_start"):
        if options.verbosity >= 5:
          print "VM %s should be running, starting..." % vm.name
        # Start machine, as if it had host pinning it couldn't be autostarted using HA
        vm.start()


if not options.cluster:
  # Processing each cluster of our RHEVM
  for cluster in api.clusters.list():
    process_cluster(cluster)
else:
  process_cluster(api.clusters.get(name=options.cluster))
