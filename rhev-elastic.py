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

import urllib2
import base64
import sys
import getopt
import optparse
import os
import time

from xml.etree import ElementTree
from random import choice

port = 8443
server = '5.97.225.61'
username = 'admin@internal'
password = 'admin'
action = "pm-suspend"
verbose = True

p = optparse.OptionParser()
p.add_option("-u", "--user", dest="username",help="Username to use", metavar="username")
p.add_option("-w", "--password", dest="password",help="Password to use", metavar="password")
p.add_option("-s", "--server", dest="server",help="RHEV-M server to contact", metavar="server")
p.add_option("-p", "--port", dest="port",help="API port to contact", metavar="port")
p.add_option("-a", "--action", dest="action",help="Power action to execute", metavar="action")
p.add_option("-v", "--verbose", dest="verbose",help="Show messages while running (True/False)", metavar="verbose")
(options, args) = p.parse_args()

baseurl="https://%s:%s" % (server,port)

# Goals:
# Tag every host to be managed previously and do not manage any host without that tag
# From n virtualization hosts, have at least 1 host without VM's up and running and the remaining ones on pm-suspend or poweroff
# This should mean:
# - If you have one VM running, you'll need one host up for the VM, another host up without VM,and n-2 hosts in maintenance + poweraction
# - If you have no running VM's, you'll need one host up without VM's and n-1 hosts in maintenance + poweraction
# - If you have host 1 full of VM's and next VM starts on second host, at
#   next check, a new host will be powered on and put online and n-3 hosts
#   will be in maintenance + poweraction state
# - If you have one VM running and put active host into maintenance, VM's
#   will migrate to active host without VM's, and a next check, another host
#   will be activated
# - If a host has been put on maintenance and has no tag, it will not be activated by the script
# - Any active host must have no tags on it (that would mean user-enabled, and should have the tag removed)
#

# tags behaviour
# elas_manage: manage this host by using the elastic management script (EMS)
# elas_maint : this host has been put on maintenance by the EMS



def apiread(target):
  URL=baseurl+target
  request = urllib2.Request(URL)
  base64string = base64.encodestring('%s:%s' % (username, password)).strip()
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
  base64string = base64.encodestring('%s:%s' % (username, password)).strip()
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
  base64string = base64.encodestring('%s:%s' % (username, password)).strip()
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

  if verbose:
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
  if verbose:
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
    comando="ssh -o ServerAliveInterval=10 -i /etc/pki/rhevm/keys/rhevm_id_rsa root@%s %s " % (host,action)
    if verbose:
      print "Sending %s the power action %s" % (host,action)
    os.system(comando)

  return
  
def activate_host(target):
  # Activate  one host at a time...
  if verbose:
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
    if verbose:
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





################################# TEST AREA #########################


  
  
################################ MAIN PROGRAM ############################
#Check if we have defined needed tags and create them if missing
check_tags

#Sanity checks
## Check hosts with elas_maint tag and status active
list=apiread("/api/hosts?search=tag%3Delas_maint")
for item in list:
  lista = apiread(item.attrib["href"])
  if host_state(lista.get("id")) == "up":
    if verbose:
      print "Host %s is tagged as elas_maint and it's active, removing tag..." % lista.get("id")
    uri=lista.get("href")+"/tags/"+tagfind("elas_maint")
    apidelete(uri)
    # Emptying powerable host list:

powerable=[]

#Check hosts with elas_manage tag associated and no SPM
list=apiread("/api/hosts?search=tag%3Delas_manage")
for item in list:
  lista = apiread(item.attrib["href"])
  vms=lista.find("summary").find("total").text
  if vms == "0":
    if host_state(lista.get("id")) == "up":
      if not is_spm(lista.get("id")):
        powerable.append(lista.get("id"))
   
if verbose:
  print "\nHost list to manage:"
  print powerable

#### Remove at least one host from the list
#### CODE TO CHECK HOST COUNT, Host still active, etc 
try:
  target=choice(powerable)
  print "Destiny has choosen as target %s" % target
  #### Deactivate host
  deactivate_host(target)
  time.sleep(10)
  activate_host(target)
except:
  if verbose:
    print "No host to manage, exiting"
  sys.exit(0)
