#!/bin/bash

echo "Current directory:"
echo $PWD
REPORT_DIR=`mktemp -d ceph_ses_bench.XXXXXXX`

# hack to fix the ssd info 
# sudo salt "node*" cmd.run 'echo 0 > /sys/block/sdb/queue/rotational'
echo "Show disk information, stop if you see something not normal" 
sudo salt "node*" ceph_sles.disk_info 
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
echo "Create journal ssd partition:"
sudo salt -L "node1 node2 node3" ceph_sles.prep_osd_journal /dev/sda 40G > $PWD/$REPORT_DIR/mount_ssd_journal.log
echo "Done!" 
echo "Prepare OSD for all node:" 
sudo salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb,/dev/sdc" > $PWD/$REPORT_DIR/clean_disk_partition.log
sudo salt "salt-master" ceph_sles.prep_osd "node1,node2,node3" "/dev/sdb,/dev/sdc" > $PWD/$REPORT_DIR/prep_osd.log
echo "Done!"
echo "Update OSD crushmap for ssd, hdd and mix ruleset:" 
sudo salt "salt-master" ceph_sles.crushmap_update_disktype_ssd_hdd node1 node2 node3
echo "Done!"

echo "Create radosgw in salt-master :" 
sudo salt "salt-master" ceph_sles.create_rados_gateway salt-master >  $PWD/$REPORT_DIR/create_gateway.log
sudo salt "salt-master" ceph_sles.push_conf node1 node2 node3 >>  $PWD/$REPORT_DIR/create_gateway.log
echo "Done!"

echo "Restarting all mon with new radosgw conf:" 
sudo salt "node*" service.restart ceph-mon@*
echo "Done!"

echo "Create S3 access user 'alex':" 
radosgw-admin user create --uid="alex" --display-name="AvengerMoJo" --email="alau@suse.com"
echo "Done!"

echo "Create Swift access user 'alex':" 
radosgw-admin subuser create --uid="alex" --subuser="alex:swift" --access="full"
radosgw-admin key create --subuser="alex:swift" --key-type="swift" --gen-secret
echo "Done!"


