#!/bin/bash 
#
# Description: Sample backup script for RHEVM infrastructure tested on 3.1
# Author: Pablo Iranzo Gómez (Pablo.Iranzo@gmail.com)
#
#

RUTALOCAL="/var/lib/pgsql/rhevm" 

FILECONFIG="$RUTALOCAL/config_$(date '+%Y%m%d_%R').tar.bz2" 
FILEREPORT="$RUTALOCAL/dump_RHEVREPORTDB_BACKUP_$(date '+%Y%m%d_%R').sql.gz" 
FILEREPORTHIST="$RUTALOCAL/dump_RHEVREPORTHISTDB_BACKUP_$(date '+%Y%m%d_%R').sql.gz" 

RUTA=/var/backup/rhevm 


# Restore files with:
# /usr/bin/pg_restore -d $DDBB -c -U postgres < /path/to/DDBB_dump

# Do not edit... only after each RHEV updated after checking new/modified configuration files for that release
FICHEROSALVA="/etc/ovirt-engine/ /etc/sysconfig/ovirt-engine /etc/yum/pluginconf.d/versionlock.list  /etc/pki/ovirt-engine/   /var/lib/ovirt-engine/backups  /var/lib/ovirt-engine/deployments  /usr/share/ovirt-engine-reports/default_master.properties  /root/.rnd  /usr/share/ovirt-engine-reports/reports/users/rhevm-002dadmin.xml /usr/share/jasperreports-server-pro/buildomatic"






#Create folders just in case... (to be clustered friendly)
[ -d $RUTALOCAL ] || exit 1

echo "Cleaning up files older than 7*24 hours"
tmpwatch $((7*24)) $RUTALOCAL

# Get into RHEV 3.1 supported backup script
cd /usr/share/ovirt-engine/dbscripts
sh backup.sh -l $RUTALOCAL -u postgres

# Compress sql dumps
gzip $RUTALOCAL/*.sql

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

echo "Output file is $FILEREPORTHIST" 
/usr/bin/pg_dump -C -E UTF8  --disable-triggers -U postgres --format=p --compress=9 -f "$FILEREPORTHIST" ovirt_engine_history
SALIDA="$?" 
if [ "$SALIDA" == "0" ]
then
	echo "Generated OK"
else
	echo "Generation failed, removing file"
	rm -f "$FILEREPORTHIST"
fi
