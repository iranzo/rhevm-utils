#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Script for setting the keyring password for RHEV scripts
#
# Requires: python keyring
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import optparse
import keyring

from rhev_functions import *

description = """
RHEV-keyring is a script for mantaining the keyring used by rhev script for storing password

"""

# Option parsing
p = optparse.OptionParser("rhev-clone.py [arguments]", description=description)
p.add_option("-u", "--user", dest="username", help="Username to connect to RHEVM API", metavar="admin@internal",
             default=False)
p.add_option("-w", "--password", dest="password", help="Password to use with username", metavar="admin",
             default=False)
p.add_option("-W", action="store_true", dest="askpassword", help="Ask for password", metavar="admin", default=False)
p.add_option('-q', "--query", action="store_true", dest="query", help="Query the values stored", default=False)

(options, args) = p.parse_args()

if options.askpassword:
    options.password = getpass.getpass("Enter password: ")

# keyring.set_password('redhat', 'kerberos', '<password>')
# remotepasseval = keyring.get_password('redhat', 'kerberos')

if options.query:
    print "Username: %s" % keyring.get_password('rhevm-utils', 'username')
    print "Password: %s" % keyring.get_password('rhevm-utils', 'password')

if options.username:
    keyring.set_password('rhevm-utils', 'username', options.username)
if options.password:
    keyring.set_password('rhevm-utils', 'password', options.password)
