#!/bin/bash

echo "Current directory:"
echo $PWD
REPORT_DIR=`mktemp -d ceph_ses_bench.XXXXXXX`

# hack to fix the ssd info 
sudo salt "node*" cmd.run 'echo 0 > /sys/block/sdb/queue/rotational'
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
sudo salt "node*" ceph_sles.create_keys_all > $PWD/$REPORT_DIR/push_conf.log
echo "Done!"
#echo "Create journal ssd partition:"
#sudo salt -L "node1 node2 node3" ceph_sles.prep_osd_journal /dev/sda 40G > $PWD/$REPORT_DIR/mount_ssd_journal.log
echo "Done!" 
echo "Prepare OSD for all node:" 
sudo salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb,/dev/sdc" > $PWD/$REPORT_DIR/clean_disk_partition.log
sudo salt "salt-master" ceph_sles.prep_osd "node1,node2,node3" "/dev/sdb,/dev/sdc" > $PWD/$REPORT_DIR/prep_osd.log
echo "Done!"
echo "Update OSD crushmap for ssd, hdd and mix ruleset:" 
sudo salt "salt-master" ceph_sles.crushmap_update_disktype_ssd_hdd node1 node2 node3
echo "Done!"
sudo ceph osd pool create ec_hdd 64 64 erasure default hdd_erasure
sudo salt "salt-master" ceph_sles.create_pool ssd_cache 64 2 ssd_replicated replicated
sudo ceph osd tier add ec_hdd ssd_cache
sudo ceph osd tier cache-mode ssd_cache writeback
sudo ceph osd tier set-overlay ec_hdd ssd_cache 
sudo ceph osd pool set ssd_cache hit_set_type bloom
sudo ceph osd pool set ssd_cache hit_set_count 1
sudo ceph osd pool set ssd_cache hit_set_period 600
#sudo ceph osd pool set ssd_cache target_max_bytes 2000000000000
sudo ceph osd pool set ssd_cache target_max_bytes 2147483648
sudo ceph osd pool set ssd_cache target_max_objects 2097152 



rbd create --size 2G ec_hdd/rbd_ec_test
rados -p ec_hdd bench 200 write -t 16 --no-cleanup
rados -p ec_hdd bench 100 seq -t 16 --no-cleanup
rados -p ec_hdd bench 100 rand -t 16 --no-cleanup
