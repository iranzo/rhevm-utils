#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for elastic management (EMS) of RHEV-H/RHEL hosts for
# RHEVM based on Douglas Schilling Landgraf <dougsland@redhat.com> scripts
# for ovirt (https://github.com/dougsland/ovirt-restapi-scripts.git)
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
# - Do not manage any host without tag elas_manage
# - Operate on one host per execution, exitting after each change
# - Have at least one host up without vm's to hold new VM's
# - Shutdown/suspend hosts without vm's untile there's only one left
# - If a host has been put on maintenance and has no tag, it will not be activated by the script
# - Any active host must have no tags on it (that would mean user-enabled, and should have the tag removed)


# tags behaviour
#	 elas_manage: manage this host by using the elastic management script (EMS)
#	 elas_maint : this host has been put on maintenance by the EMS

import urllib
import urllib2
import base64
import sys
import getopt
import optparse
import os
import time

from xml.etree import ElementTree
from random import choice


description="""
RHEV-Elastic is a script for managing via API the hypervisors under RHEV command, both RHEV-H and RHEL hosts.

It's goal is to keep the higher amount of hosts turned off or suspended in
order to save energy, automatically activating or deactivating hosts when
needed in order to satisfy your environment needs.

"""

# Option parsing
p = optparse.OptionParser("rhev-elastic.py [arguments]",description=description)
p.add_option("-u", "--user", dest="username",help="Username to connect to RHEVM API", metavar="admin@internal",default="admin@internal")
p.add_option("-w", "--password", dest="password",help="Password to use with username", metavar="admin",default="admin")
p.add_option("-s", "--server", dest="server",help="RHEV-M server address/hostname to contact", metavar="127.0.0.1",default="127.0.0.1")
p.add_option("-p", "--port", dest="port",help="API port to contact", metavar="8443",default="8443")
p.add_option("-a", "--action", dest="action",help="Power action to execute", metavar="action",default="pm-suspend")
p.add_option('-v', "--verbosity", dest="verbosity",help="Show messages while running", metavar='[0-n]', default=0,type='int')
p.add_option('-t', "--tagall", dest="tagall",help="Tag all hosts with elas_manage", metavar='0/1', default=0,type='int')

(options, args) = p.parse_args()

baseurl="https://%s:%s" % (options.server,options.port)


#FUNCTIONS

def apiread(target):
  URL=baseurl+target
  request = urllib2.Request(URL)
  base64string = base64.encodestring('%s:%s' % (options.username, options.password)).strip()
  request.add_header("Authorization", "Basic %s" % base64string)

  try:
    xmldata = urllib2.urlopen(request).read()
  except urllib2.URLError, e:
    print "Error: cannot connect to REST API: %s" % (e)
    print "\tTry to login using the same user/pass by the Admin Portal and check the error!"
    sys.exit(2)
  return ElementTree.XML(xmldata)

def apiwrite(target,xml_request):
  URL=baseurl+target
  request = urllib2.Request(URL)
  base64string = base64.encodestring('%s:%s' % (options.username, options.password)).strip()
  request.add_header("Authorization", "Basic %s" % base64string)
  request.add_header("Content-type", "application/xml")
  
  try:
    xmldata = urllib2.urlopen(request,xml_request)
  except urllib2.URLError, e:
    print "Error: cannot connect to REST API: %s" % (e)
    print "\tTry to login using the same user/pass by the Admin Portal and check the error!"
    sys.exit(2)
  return xmldata
  
def apidelete(target):
  URL=baseurl+target
  request = urllib2.Request(URL)
  base64string = base64.encodestring('%s:%s' % (options.username, options.password)).strip()
  request.add_header("Authorization", "Basic %s" % base64string)
  request.add_header("Content-type", "application/xml")
  request.get_method = lambda: 'DELETE'
  
  try:
    xmldata = urllib2.urlopen(request)
  except urllib2.URLError, e:
    print "Error: cannot connect to REST API: %s" % (e)
    print "\tTry to login using the same user/pass by the Admin Portal and check the error!"
    sys.exit(2)
  return xmldata
  
  
def tagfind(tag):
  tagid=''
  list = apiread("/api/tags")
  
  for item in list:
    lista = apiread(item.attrib["href"])
    for elem in lista:
      if elem.tag == "name":
        if elem.text == tag:
          tagid = lista.attrib["id"]
  return tagid

def check_tags():
  list = apiread("/api/tags")

  if options.verbosity >= 1:
    print "Looking for tags elas_manage and elas_maint prior to start..."

  elas_maint=tagfind("elas_maint")
  elas_manage=tagfind("elas_manage")

  if elas_maint == '':
    xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
	<tag>
	  <name>elas_maint</name>
	</tag>
	"""
    apiwrite("/api/tags",xml_request)
    elas_maint=tagfind("elas_maint")
  
  if elas_manage == '':
    xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
	<tag>
	  <name>elas_manage</name>
	</tag>
	"""
    apiwrite("/api/tags",xml_request)
    elas_manage=tagfind("elas_manage")

  return  
  
def host_state(target):
  uri="/api/hosts/%s" % target
  list=apiread(uri)
  return list.find("status").find("state").text

def has_tag(target,tag):
  encontrado=False
  uri="%s/tags" % target
  list=apiread(uri)
  for elem in list:
    if elem.get("id") == tag:
      encontrado=True
      break
  return encontrado
  
def is_spm(target):
  encontrado=False
  uri="/api/hosts/%s" % target
  list=apiread(uri)
  if list.find("storage_manager").text=="true":
    encontrado=True
  return encontrado
  
def deactivate_host(target):
  # Shutting down one host at a time...
  if options.verbosity > 0:
    print "Shutting down target %s" % target

  #Add elas_maint TAG to host
  uri="/api/hosts/%s/tags" % target
  xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
  <tag>
    <name>elas_maint</name>
  </tag>
  """
  apiwrite(uri,xml_request)

  #Set host on maintenance
  uri="/api/hosts/%s/deactivate" % target
  xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
  <action/>
  """
  apiwrite(uri,xml_request)

  #Get host IP
  uri="/api/hosts/%s" % target
  list=apiread(uri)
  for item in list:
    host=list.find("address").text
    
  #Should wait until host state is 'maintenance'
  time.sleep(30)
  
  if host_state(target) == "maintenance":
    #Execute power action
    ## /etc/pki/rhevm/keys/rhevm_id_rsa
    comando="ssh -o ServerAliveInterval=10 -i /etc/pki/rhevm/keys/rhevm_id_rsa root@%s %s " % (host,options.action)
    if options.verbosity >= 1:
      print "Sending %s the power action %s" % (host,options.action)
    os.system(comando)

  return
  
def activate_host(target):
  # Activate  one host at a time...
  if options.verbosity > 0:
    print "Activating target %s" % target
   
  #Remove elas_maint TAG to host
  url="/api/hosts/%s" % target
  uri=url + "/tags/%s" % tagfind("elas_maint")   

  if has_tag(url,tagfind("elas_maint")) == True:
    apidelete(uri)  

  #Get Host MAC
  uri="/api/hosts/%s/nics" % target
  list=apiread(uri)
  for nic in list:
    mac=nic.find("mac").get("address")
    # By default, send wol using every single nic at RHEVM host
    comando="for tarjeta in $(for card in $(ls -d /sys/class/net/*/);do echo $(basename $card);done);do ether-wake -i $tarjeta %s ;done" %mac
    if options.verbosity >= 1:
      print "Sending %s the power on action via %s" % (target,mac)
    os.system(comando)    

  if host_state(target) == "maintenance":
    #Activate host
    uri="/api/hosts/%s/activate" % target
    xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <action/>
    """
    apiwrite(uri,xml_request)

  return  

def process_cluster(clusid):
  if options.verbosity > 1:
    print "\nProcessing cluster with id %s" % clusid
    print "#############################################################################"

  #Emptying maintanable and activable hosts list
  maintable=[]
  enablable=[]

  hosts_total=0
  hosts_up=0
  hosts_maintenance=0
  hosts_other=0
  hosts_without_vms=0
  hosts_with_vms=0
    
  list=apiread("/api/hosts?search=elas_manage")
  for item in list:
    lista = apiread(item.attrib["href"])
    vms=lista.find("summary").find("total").text
    status="discarded"
    inc=1
  
    if item.find("cluster").get("id") != clusid:
      # Not process this host if doesn't pertain to cluster
      if options.verbosity >= 3:
        print "Host %s doesn't pertain to cluster %s" % (lista.get("id"),clusid)
        
    else:

      #Preparing list of valid hosts  
      if vms == "0": 
        if host_state(lista.get("id")) == "up":
          if not is_spm(lista.get("id")):
            maintable.append(lista.get("id"))
            status="accepted"
        if host_state(lista.get("id")) == "maintenance":
          url="/api/hosts/%s" % lista.get("id")
          if has_tag(url,tagfind("elas_maint")):
            enablable.append(lista.get("id"))
            status="accepted"
          else:
            status="No elas_maint tag discarded"
            inc=0
      if options.verbosity >= 2:
        print "Host (%s) %s with %s vms detected with status %s and spm status %s (%s for operation)" % (lista.find("name").text,lista.get("id"),vms,host_state(lista.get("id")),is_spm(lista.get("id")),status)

      #Counters
      hosts_total=hosts_total+inc
 
      if host_state(lista.get("id")) == "up":
        hosts_up=hosts_up+inc
        if vms == "0":
          hosts_without_vms=hosts_without_vms+inc
        else:
          hosts_with_vms=hosts_with_vms+inc
      else:
        if host_state(lista.get("id")) == "maintenance":
          hosts_maintenance=hosts_maintenance+inc
        else:
          hosts_other=hosts_other+inc
   
  if options.verbosity >= 1:
      print "\nHost list to manage:"
      print "\tCandidates to maintenance: %s" % maintable
      print "\tCandidates to activation:  %s" % enablable
      print "\nHosts TOTAL (Total/Up/Maintenance/other): %s/%s/%s/%s" % (hosts_total,hosts_up,hosts_maintenance,hosts_other)
      print "Hosts    UP (with VM's/ without):  %s/%s" % (hosts_with_vms,hosts_without_vms)

  #### CODE TO CHECK HOST COUNT, Host still active, etc 

  #Useful vars:   hosts_total,hosts_up,hosts_maintenance,hosts_other,hosts_with_vms,hosts_without_vms
  #Useful arrays: enablable / maintable


  ################################# ENABLE SECTION #########################################

  #At least one host but no one is up -> enable one host
  if hosts_total > 0 and hosts_up == 0:
    try:
      target=choice(enablable)
      if options.verbosity >= 2:
        print "\nActivating host %s because no one is up\n" % target
      activate_host(target)
      return 0
    except:
      if options.verbosity >= 1:
        print "\nNo host to enable\n"
      return 1

  #Host active without vm's
  if hosts_up > 0:
  #At least one host up without vm's:
    if hosts_without_vms == 0:
      try:
        target=choice(enablable)
        if options.verbosity >= 2:
          print "\nActivating host %s because there are no hosts without vm's\n" % target
              
        activate_host(target)
        return 0
      except:
        print "\nNo host to enable\n"
        return 1
    
      
  ############################### DISABLE SECTION ########################################
      
  if hosts_without_vms > 1:
    #More than one host without VM's so we can shutdown one
    try:
      target=choice(maintable)
      if options.verbosity >= 2:
        print "\nPutting host %s into maintenance because there are more than 1 host without vm's\n" % target
      deactivate_host(target)
      return 0
    except:
      print "\nNo host to put into maintenance\n"
      return 1
  
  #############################  NOTHING TO DO SECTION ###################################
  
  if options.verbosity >= 2:
    print "\nNothing to do as enable/disable scripts conditions are not met"
  
  return


################################ MAIN PROGRAM ############################
#Check if we have defined needed tags and create them if missing
check_tags()


# TAGALL?
#Add elas_maint TAG to every single host to automate the management
if options.tagall == 1:

  if options.verbosity >=1:
    print "Tagging all hosts with elas_manage"
    
  list=apiread("/api/hosts")
  for item in list:
    target=item.get("id")
    uri="/api/hosts/%s/tags" % target
    xml_request ="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <tag>
      <name>elas_manage</name>
    </tag>
    """
    apiwrite(uri,xml_request)

#Sanity checks
## Check hosts with elas_maint tag and status active
list=apiread("/api/hosts?search=elas_maint")
for item in list:
  lista = apiread(item.attrib["href"])
  if host_state(lista.get("id")) == "up":
    if options.verbosity >= 1:
      print "Host %s is tagged as elas_maint and it's active, removing tag..." % lista.get("id")
    uri=lista.get("href")+"/tags/"+tagfind("elas_maint")
    apidelete(uri)

# Processing each cluster of our RHEVM
list=apiread("/api/clusters")
for cluster in list:
  process_cluster(cluster.get("id"))
