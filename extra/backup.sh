#!/bin/bash 
#
# Description: Sample backup script for RHEVM infrastructure
# Author: Pablo Iranzo Gómez (Pablo.Iranzo@redhat.com)
#
#

RUTALOCAL="/usr/share/rhevm/db-backups" 
FILE="$RUTALOCAL/dump_RHEVDB_BACKUP_$(date '+%Y%m%d_%R').sql.gz" 
FILEREPORT="$RUTALOCAL/dump_RHEVREPORTDB_BACKUP_$(date '+%Y%m%d_%R').sql.gz" 
FILEREPORTHIST="$RUTALOCAL/dump_RHEVREPORTHISTDB_BACKUP_$(date '+%Y%m%d_%R').sql.gz" 

FILECONFIG="$RUTALOCAL/config_$(date '+%Y%m%d_%R').tar.bz2" 
RUTA=/var/backup/rhevm 


# Restore files with:
# /usr/bin/pg_restore -d $DDBB -c -U postgres < /path/to/DDBB_dump

# Do not edit... only after each RHEV updated after checking new/modified configuration files for that release
REPORT_VERSION=$(ls -d /usr/share/rhevm-reports/reports-*|sort |tail -1) 
FICHEROSALVA="/etc/jbossas/jbossas.conf /etc/jbossas/rhevm-slimmed/ /etc/pki/rhevm/ /etc/rhevm/ /etc/yum/pluginconf.d/versionlock.list /root/.pgpass /root/.rnd /usr/share/rhevm/conf/iptables.example /usr/share/rhevm/dbscripts/create_db.sh.log $REPORT_VERSION/resources/organizations/rhevmreports/Resources/JDBC/data_sources/rhevm.xml $REPORT_VERSION/users/rhevmreports/rhevm-002dadmin.xml /usr/share/rhevm-reports-server/buildomatic /usr/share/rhevm-reports-server/buildomatic/default_master.properties /usr/share/rhevm-reports-server/buildomatic/install.xml /usr/share/rhevm-reports-server/buildomatic/setup.xml /usr/share/rhevm/rhevm.ear/rhevmanager.war/ExternalConfig.txt /usr/share/rhevm/rhevm.ear/rhevmanager.war/ServerParameters.js" 


echo "Cleaning up files older than 7*24 hours"

TIME=$(echo 7*24|bc)

#Create folders just in case...
mkdir -p $RUTALOCAL
mkdir -p $RUTA

tmpwatch $TIME $RUTALOCAL

echo "Output file is $FILE" 
/usr/bin/pg_dump -C -E UTF8  --disable-triggers -U postgres --format=p --compress=9 -f "$FILE" rhevm 
SALIDA="$?" 
if [ "$SALIDA" == "0" ]
then
	echo "Generated OK"
else
	echo "Generation failure, removing file"
	rm -f "$FILE"
fi

echo "Output file is $FILEREPORT" 
/usr/bin/pg_dump -C -E UTF8  --disable-triggers -U postgres --format=p --compress=9 -f "$FILEREPORT" rhevmreports
SALIDA="$?" 
if [ "$SALIDA" == "0" ]
then
	echo "Generated OK"
else
	echo "Generation failed, removing file"
	rm -f "$FILEREPORT"
fi

echo "Output file is $FILEREPORTHIST" 
/usr/bin/pg_dump -C -E UTF8  --disable-triggers -U postgres --format=p --compress=9 -f "$FILEREPORTHIST" rhevm_history
SALIDA="$?" 
if [ "$SALIDA" == "0" ]
then
	echo "Generated OK"
else
	echo "Generation failed, removing file"
	rm -f "$FILEREPORTHIST"
fi


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
