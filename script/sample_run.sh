#!/bin/bash

echo "Current directory:"
echo $PWD
REPORT_DIR=`mktemp -d ceph_ses_bench.XXXXXXX`

echo "Create $REPORT_DIR for storage bench report"

echo "Reading node disk info:"
sudo salt "node*" ceph_sles.disk_info > $PWD/$REPORT_DIR/disk_info.txt
echo "Done!"
echo "Reading individual disk read speed:"
sudo salt "node*" ceph_sles.bench_disk /dev/sda /dev/sdb > $PWD/$REPORT_DIR/bench_disk.txt
echo "Done!"
echo "Reading individual node hardware information :"
sudo salt "node*" ceph_sles.profile_node > $PWD/$REPORT_DIR/node_profile.txt
echo "Done!"
echo "Reading network benchmark from nodes:"
sudo salt -L "salt-master node1 node2 node3" ceph_sles.bench_network salt-master node1 node2 node3 > $PWD/$REPORT_DIR/bench_network.txt
echo "Done!"
echo "Sync time before starting mon:"
sudo salt "node*" ceph_sles.ntp_update salt-master > $PWD/$REPORT_DIR/ntp_sync.log
echo "Done!"
echo "Create ceph new mon nodes:"
sudo salt "salt-master" ceph_sles.new_mon node1 node2 node3 > $PWD/$REPORT_DIR/new_mon.log
echo "Done!"
echo "Push config file over to salt-master:"
sudo salt "salt-master" ceph_sles.push_conf salt-master  > $PWD/$REPORT_DIR/push_conf.log
echo "Done!"
# echo "Create journal ssd partition:"
# sudo salt -L "node1 node2 node3" ceph_sles.prep_osd_journal /dev/sda 40G > $PWD/$REPORT_DIR/mount_ssd_journal.log
# echo "Done!" 
echo "Prepare OSD for all node:" 
sudo salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb" > $PWD/$REPORT_DIR/clean_disk_partition.log
sudo salt "salt-master" ceph_sles.prep_osd "node1,node2,node3" "/dev/sdb" > $PWD/$REPORT_DIR/prep_osd.log
echo "Done!"
echo "Update OSD crushmap for ssd, hdd and mix ruleset:" 
sudo salt "salt-master" ceph_sles.crushmap_update_disktype_ssd_hdd node1 node2 node3
echo "Done!"
echo "Starting rados bench, go get tea and come back in 2 hours:" 
sudo salt "salt-master" ceph_sles.bench_rados
echo "Done!"




