#!/usr/bin/env python
#
# Author: Pablo Iranzo Gomez (Pablo.Iranzo@redhat.com)
#
# Description: Basic common set of functions for usage in other scripts
#
# Requires rhevm-sdk to work
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.

import getpass
import sys
import time

from ovirtsdk.api import API
from ovirtsdk.xml import params


# FUNCTIONS
def getuserpass(options):
    """Checks if it should ask for password interactively, use the keyring or just return the default values or
    commandline values provided by arguments.

    @param options: Options gathered from the script executed by user
    """
    if options.keyring:
        import keyring
        options.username = keyring.get_password('rhevm-utils', 'username')
        options.password = keyring.get_password('rhevm-utils', 'password'),
    elif options.askpassword:
        options.password = getpass.getpass("Enter password: ")
    return options.username, options.password


def check_version(api, major, minor):
    """Checks if required version or higher is installed
    @param api: points to API object to reuse access
    @param major: Major version for available RHEV-H release
    @param minor: Minor  version for available RHEV-H release
    """
    valid = False
    if api.get_product_info().version.major >= major:
        if api.get_product_info().version.minor >= minor:
            valid = True
    return valid


def apilogin(url, username, password, insecure=True, persistent_auth=True, session_timeout=36000):
    """
    @param url: URL for RHEV-M  / Ovirt
    @param username: username to use
    @param password: password for username
    @param insecure: if True, do not validate SSL cert
    @param persistent_auth: Use persistent authentication
    @param session_timeout: Session timeout for non-persistent authentication
    @return:
    """
    api = None

    try:
        api = API(url=url, username=username, password=password, insecure=insecure, persistent_auth=persistent_auth,
                  session_timeout=session_timeout)
    except:
        print("Error while logging in with supplied credentials, please check and try again")
        sys.exit(1)

    return api


def check_tags(api, options):
    """Checks if required tags have been already defined and creates them if missing

    @param api: points to API object to reuse access
    @param options: points to options object to reuse values provided on parent
    """
    if options.verbosity >= 1:
        print("Looking for tags prior to start...")

    tags = "elas_maint elas_manage elas_start elas_upgrade "

    for tag in tags:
        if not api.tags.get(name=tag):
            if options.verbosity >= 2:
                print "Creating tag %s..." % tag
            api.tags.add(params.Tag(name=tag))

    return


def migra(api, options, vm, action=None):
    """Initiates migration action of the vm to specified host or automatically if None
    @param api: points to API object to reuse access
    @param options: points to options object to reuse values provided on parent
    @param action: host to migrate the VM to or use default
    @param vm: vm to work on
    """
    if not action:
        try:
            vm.migrate()
        except:
            if options.verbosity > 4:
                print("Problem migrating auto %s" % vm.name)
    else:
        try:
            vm.migrate(action)
        except:
            if options.verbosity > 4:
                print("Problem migrating fixed %s" % vm.name)

    loop = True
    counter = 0
    while loop:
        if vm.status.state == "up":
            loop = False
        if options.verbosity > 8:
            print("VM migration loop %s" % counter)
        time.sleep(10)
        counter += 1

        if counter > 12:
            loop = False
            if options.verbosity > 8:
                print("Exiting on max loop retries")
    return


def vmused(api, vm):
    """Returns amount of memory used by the VM from Agent if installed or configured if not
    @param api: points to API object to reuse access
    @param vm: vm to work on
    """
    # Get memory usage from agent
    used = vm.statistics.get("memory.used").values.value[0].datum
    if used == 0:
        # If no value received, return installed memory
        used = vm.statistics.get("memory.installed").values.value[0].datum

    return used


def paginate(element, oquery=""):
    """
    Paginates results of .list() for an object to avoid api limitations,
    it is created as generator to improve performance.

    @param element: points to api object for reuse
    @param oquery:  optional query to pass to limit search results
    """

    page = 0
    length = 100
    while length > 0:
        page += 1
        query = "%s page %s" % (oquery, page)
        tanda = element.list(query=query)
        length = len(tanda)
        for elem in tanda:
            yield elem


if __name__ == "__main__":
    print("This file is intended to be used as a library of functions and it's not expected to be executed directly")
