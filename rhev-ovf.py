#!/usr/bin/env python
#
# Description: Parse ovf to start VM
# Author: Pablo.Iranzo@gmail.com
#
# Based on Karim Boumedhel's code at
# https://github.com/karmab/ovirt/blob/master/hypervisor.py
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
import sys
import xml.etree.ElementTree as elementtree

description = """
Parse an OVF file on disk to show the information needed to start
the VM via command line
"""

# Option parsing
p = optparse.OptionParser("rhev-ovf.py [arguments]", description=description)
p.add_option('-f', "--file", dest="file", help="OVF file to parse",
             metavar='ovf', default=None)

(options, args) = p.parse_args()


def getvminfo(host, vmid, display, root):
    """Parses XML tree to gather all the information from VM"""

    global diskdomids
    cmd = {"vmId": vmid, "kvmEnable": "True", "vmType": "kvm", "tabletEnable": "True", "vmEnable": "True",
           "irqChip": "True", "nice": 0, "keyboardLayout": "en-us", "acpiEnable": "True", "display": "qxl",
           "displayIp": host, "spiceMonitors": "1", "displayNetwork": display}
    disks = []
    diskboot = None
    diskvolid = None
    diskimageid = None
    diskformat = None
    for child in root:
        if child.tag == "Section" and "ovf:DiskSection_Type" in child.attrib.values():
            for disk in child.findall("Disk"):
                for info in disk.attrib:
                    if "boot" in info:
                        diskboot = disk.attrib[info]
                    if "fileRef" in info:
                        diskimageid, diskvolid = disk.attrib[info].split("/")
                    if "volume-format" in info:
                        diskformat = disk.attrib[info].lower()
                disks.append({"boot": diskboot, "volumeID": diskvolid,
                              "imageID": diskimageid, "format": diskformat})

    for content in root.findall("Content"):
        name = content.findall("Name")[0].text
        display = content.findall("DefaultDisplayType")[0].text
        if display != "1":
            cmd["display"] = "vnc"
        else:
            cmd["display"] = "qxl"
        sections = content.findall("Section")
        for hardware in sections:
            if "ovf:VirtualHardwareSection_Type" in hardware.attrib.values():
                macs = []
                nicnames = []
                bridges = []
                nicmodels = []
                diskdomids = []
                diskpoolids = []
                for item in hardware.findall("Item"):
                    for element in item:
                        if "num_of_sockets" in element.tag:
                            smp = element.text
                        if "cpu_per_socket" in element.tag:
                            cpuspersocket = element.text
                        if "VirtualQuantity" in element.tag:
                            memory = element.text
                        if "AllocationUnits" in element.tag:
                            memoryunits = element.text
                        if "MACAddress" in element.tag:
                            macs.append(element.text)
                        if "Name" in element.tag:
                            nicnames.append(element.text)
                        if "Connection" in element.tag:
                            bridges.append(element.text)
                        if "ResourceSubType" in element.tag:
                            if element.text == "1":
                                nicmodels.append("rtl8139")
                            if element.text == "2":
                                nicmodels.append("e1000")
                            if element.text == "3":
                                nicmodels.append("pv")
                        if "StorageId" in element.tag:
                            diskdomids.append(element.text)
                        if "StoragePoolId" in element.tag:
                            diskpoolids.append(element.text)

    counter = 0
    cmd["drives"] = []
    for disk in disks:
        cmd["drives"].append(disk)
        cmd["drives"][counter]["domainID"] = diskdomids[counter]
        cmd["drives"][counter]["poolID"] = diskpoolids[counter]
        counter += 1

    cmd["memSize"] = memory
    cmd["smpCoresPerSocket"] = cpuspersocket
    cmd["smp"] = smp
    cmd["bridge"] = ",".join(bridges)
    cmd["macAddr"] = ",".join(macs)
    cmd["vmName"] = name
    cmd["nicModel"] = ",".join(nicmodels)
    return cmd


try:
    tree = elementtree.parse(options.file)
except:
    print("Error opening the ovf file %s" % options.file)
    sys.exit(1)

root = tree.getroot()

for content in root.findall('Content'):
    vmname = content.findall("Name")[0].text
    template = content.findall("TemplateId")[0].text
    if template == "00000000-0000-0000-0000-000000000000":
        break

# Create VM
vmid = "00"
display = "spice"
host = "localhost"
cmd = getvminfo(host, vmid, display, root)

print(cmd)
