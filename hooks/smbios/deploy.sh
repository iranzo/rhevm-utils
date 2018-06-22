#!/bin/bash
#
# Description: Script for deploying scripts on hypervisor
#
# Author: Pablo Iranzo Gómez (Pablo.Iranzo@gmail.com)
#

HOST=$1
if [ "$HOST" == "" ];
then
	echo "No host specified, exiting..."
	exit 1
fi

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ] ; do SOURCE="$(readlink "$SOURCE")"; done
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"


pushd .

echo "Getting into script folder..."
cd $DIR

echo "Copying required files..."

scp -q -o StrictHostKeyChecking=no -i /etc/pki/rhevm/keys/rhevm_id_rsa before_vm_start.py  $HOST:/usr/libexec/vdsm/hooks/before_vm_start/50_smbios

echo "Changing permissions"
ssh -q -o StrictHostKeyChecking=no  -i /etc/pki/rhevm/keys/rhevm_id_rsa $HOST persist /usr/libexec/vdsm/hooks/before_vm_start/50_smbios


echo "Restarting VDSM to reflect changes"
ssh -q -o StrictHostKeyChecking=no  -i /etc/pki/rhevm/keys/rhevm_id_rsa $HOST service vdsmd restart

popd
