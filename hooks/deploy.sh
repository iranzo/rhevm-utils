#!/bin/bash
#
# Description: Script for deploying scripts on hypervisor
#
# Author: Pablo Iranzo Gómez (Pablo.Iranzo@redhat.com)
#

export PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/root/bin

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

for folder in $(ls);
do
	if [ -d "$folder" ];
	then
		echo "Getting into script folder..."
		cd $DIR/$folder
		
		echo "Deploying..."
		sh deploy.sh "$1"
	fi
	cd $DIR
done

popd
