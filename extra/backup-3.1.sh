#!/bin/bash 
#
# Description: Sample backup script for RHEVM infrastructure tested on 3.1
# Author: Pablo Iranzo Gómez (Pablo.Iranzo@redhat.com)
#
#

RUTALOCAL="/var/lib/pgsql/rhevm" 

FILECONFIG="$RUTALOCAL/config_$(date '+%Y%m%d_%R').tar.bz2" 
RUTA=/var/backup/rhevm 


# Restore files with:
# /usr/bin/pg_restore -d $DDBB -c -U postgres < /path/to/DDBB_dump

# Do not edit... only after each RHEV updated after checking new/modified configuration files for that release
FICHEROSALVA="/etc/ovirt-engine/ /etc/sysconfig/ovirt-engine /etc/yum/pluginconf.d/versionlock.list  /etc/pki/ovirt-engine/  /usr/share/ovirt-engine/dbscripts/create_db.sh.log  /var/lib/ovirt-engine/backups  /var/lib/ovirt-engine/deployments  /usr/share/ovirt-engine-reports/default_master.properties  /root/.rnd  /usr/share/ovirt-engine-reports/reports/users/rhevm-002dadmin.xml /usr/share/jasperreports-server-pro/buildomatic"





TIME=$(echo 7*24|bc)

#Create folders just in case... (to be clustered friendly)
[ -d $RUTALOCA ] || exit 1

echo "Cleaning up files older than 7*24 hours"
tmpwatch $TIME $RUTALOCAL

# Get into RHEV 3.1 supported backup script
cd /usr/share/ovirt-engine/dbscripts
sh backup.sh -l $RUTALOCAL -u postgres

echo "Output file is $FILECONFIG"
tar cjPpf $FILECONFIG $FICHEROSALVA 
SALIDA="$?" 

if [ "$SALIDA" == "0" ]
then
	echo "Generated OK"
else
	echo "Genetion failed, removing file"
	rm -f "$FILECONFIG"
fi
