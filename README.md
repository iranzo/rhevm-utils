## RHEVM-Elastic-Management Scripts

[![Build Status](https://travis-ci.org/iranzo/rhevm-utils.svg?branch=master)](https://travis-ci.org/iranzo/rhevm-utils)
[![Code Climate](https://codeclimate.com/github/iranzo/rhevm-utils/badges/gpa.svg)](https://codeclimate.com/github/iranzo/rhevm-utils)

### REQUIRES:

- rhevm-sdk >= rhevm-sdk-3.1.0.10-1.el6ev.noarch.rpm

#### OPTIONAL:

- python-keyring (if willing to store credentials)

NOTE: If you are willing to use the keyring feature, please, first setup a username/password using `rhev-keyring.py` before using `-k` argument with the remaining scripts.

Author: Pablo Iranzo Gómez (Pablo.Iranzo@gmail.com)

Contributors:

- Ian Lochrin
- Sean P Kane (https://github.com/spkane)
- Fran García (https://github.com/frangdlt)

Please, check individual README files for specific behaviour and description under doc/:

- rhev_functions.py:         Common set of functions for usage by other scripts
- rhev-keyring.py:           Script to set/query keyring values for username/password
- rhev-elastic.py:           Manage hosts and power them off if unused
- rhev-vm-cluster.py:        Use tags to migrate VM's away from each other (sort of anti-affinity)
- rhev-vlan.py:              Create VLAN with name and vlan_id on DC and associate to specified cluster and its hosts
- rhev-cleanpinning.py:      Clean VM pinning to host
- rhev-policy.py:            Change clusters policy to the one provided
- rhev-vm-os.py:             Group VM's by O.S. on hosts
- rhev-clone.py:             Create a clone VM based on a Template on a specified Cluster
- rhev-poweron.py:           Power on (remove maintenance) from all rhev_elastic hosts in maintenance in order to prepare for peak hours
- rhev-vm-start.py:          Start VM specified or remaining VM's if specified is up
- rhev-vm-create.py:         Create a new VM with specified parameters
- rhev-vm-tax.py:            Create a table with information about last month usage and configured values for CPU/RAM/HDD
- rhev-vm-applist.py:        Create a table with information about VM's and apps reported by rhev-agent

PD: Please, if you're using this scripts, send me an email just to know if
there's anyone outside there. If you find any error, please report it to me
and I'll try to get it fixed, opening a issue request on github helps to track them!

Those scripts are updated when I have the opportunity to deal with the environment, so they maybe outdated until I have the chance to update them to newer versions, and may have errors not detected when performing updates on others, please, test with care and report any issue.

Philosophy is: Release Early, Release Often, so some scripts can be ugly (no error control, etc), but provide the basic functionality, in later updates, they will be improved, and of course, pull requests are welcome.
