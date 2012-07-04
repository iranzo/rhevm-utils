#!/bin/bash
HOST=$1
if [ "$HOST" == "" ];
then
	echo "No host specified, exitting..."
	exit 1
fi

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ] ; do SOURCE="$(readlink "$SOURCE")"; done
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"


pushd .

echo "Getting into script folder..."
cd $DIR

ssh -q -o StrictHostKeyChecking=no  -i /etc/pki/rhevm/keys/rhevm_id_rsa $HOST unpersist /etc/sudoers.d/50_vdsm_hook_directlun /usr/libexec/vdsm/hooks/after_vm_destroy/50_directlun /usr/libexec/vdsm/hooks/before_vm_migrate_destination/50_directlun  /usr/libexec/vdsm/hooks/before_vm_start/50_directlun
ssh -q -o StrictHostKeyChecking=no  -i /etc/pki/rhevm/keys/rhevm_id_rsa $HOST rm /etc/sudoers.d/50_vdsm_hook_directlun /usr/libexec/vdsm/hooks/after_vm_destroy/50_directlun /usr/libexec/vdsm/hooks/before_vm_migrate_destination/50_directlun  /usr/libexec/vdsm/hooks/before_vm_start/50_directlun

echo "Restarting VDSM to reflect changes"
ssh -q -o StrictHostKeyChecking=no  -i /etc/pki/rhevm/keys/rhevm_id_rsa $HOST service vdsmd restart

popd
