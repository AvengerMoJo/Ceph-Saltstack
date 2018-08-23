#!/bin/sh 

# salt "*" grains.set deepsea default
# setup /srv/pillar/ceph/master_minion.sls

# Copy ceph-salt-script to salt-master 
cp ceph_sles.py /srv/salt/_modules/
sudo salt 'node*' saltutil.sync_all

# benchmark ping 
sudo salt-run net.ping exclude="not G@deepsea:default"
sudo salt-run net.jumbo_ping exclude="not G@deepsea:default"

# benchmark network 
sudo salt-run net.iperf exclude="not G@deepsea:default"

# benchmark harddrive 
sudo salt 'node*' ceph_sles.bench_disk /dev/sdb /dev/sdc /dev/sdd /dev/sde /dev/sdf /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl
sudo salt "node*" ceph_sles.bench_disk /dev/sdm /dev/sdn /dev/sdo /dev/sdp /dev/sdq /dev/sdr /dev/sds /dev/sdt /dev/sdu /dev/sdv /dev/sdw

# zap disk 
sudo salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb,/dev/sdc,/dev/sdd,/dev/sde,/dev/sdf,/dev/sdg,/dev/sdh,/dev/sdi,/dev/sdj,/dev/sdk,/dev/sdl"
sudo salt "node*" ceph_sles.clean_disk_partition "/dev/sdm,/dev/sdn,/dev/sdo,/dev/sdp,/dev/sdq,/dev/sdr,/dev/sds,/dev/sdt,/dev/sdu,/dev/sdv,/dev/sdw"

# create bcache 

parted -s -a optimal /dev/nvme0n1 mkpart primary 0G 350G
parted -s -a optimal /dev/nvme1n1 mkpart primary 0G 350G

salt "node*" ceph_sles.make_bcache /dev/nvme0n1p1 /dev/sdb /dev/sdc /dev/sdd /dev/sde /dev/sdf /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl

for i in `seq 0 11`; do echo writeback > /sys/block/bcache$i/bcache/cache_mode; done
for i in `seq 0 11`; do echo 512k > /sys/block/bcache$i/bcache/sequential_cutoff; done
for i in `seq 0 11`; do echo 40 > /sys/block/bcache$i/bcache/writeback_percent; done

salt "node*" ceph_sles.make_bcache /dev/nvme1n1p1 /dev/sdm /dev/sdn /dev/sdo /dev/sdp /dev/sdq /dev/sdr /dev/sds /dev/sdt /dev/sdu /dev/sdv /dev/sdw 
for i in `seq 12 22`; do echo writeback > /sys/block/bcache$i/bcache/cache_mode; done
for i in `seq 12 22`; do echo 512k > /sys/block/bcache$i/bcache/sequential_cutoff; done
for i in `seq 12 22`; do echo 40 > /sys/block/bcache$i/bcache/writeback_percent; done

echo "policy.cfg get to be send" 
echo "cp node1.yml /srv/pillar/ceph/proposals/profile-default/stack/default/ceph/minions/*" 
echo "cp node2.yml /srv/pillar/ceph/proposals/profile-default/stack/default/ceph/minions/*" 
echo "cp node3.yml /srv/pillar/ceph/proposals/profile-default/stack/default/ceph/minions/*" 
echo "cp node4.yml /srv/pillar/ceph/proposals/profile-default/stack/default/ceph/minions/*" 
echo "cp node5.yml /srv/pillar/ceph/proposals/profile-default/stack/default/ceph/minions/*" 

# load empty node.yml 
echo "Make sure db size is set in conf?" 
# ceph-conf --show-config | grep bluestore |grep size  |grep wal

# create ceph-disk prepare with bcache by script 
NVME=nvme0n1
for i in `seq 0 11`; do
    ceph-disk prepare --bluestore /dev/bcache$i --block.db /dev/$NVME --block.wal /dev/$NVME --osd.id $i
done
NVME=nvme1n1
for i in `seq 12 22`; do
    ceph-disk prepare --bluestore /dev/bcache$i --block.db /dev/$NVME --block.wal /dev/$NVME --osd.id $i
done

# create pool class HPE 
for i in `seq 0 11`; do
    ceph osd crush rm-device-class osd.$i
    ceph osd crush set-device-class HPE-hdd osd.$i
done
for i in `seq 12 22`; do
    ceph osd crush rm-device-class osd.$i
    ceph osd crush set-device-class HPE-hdd osd.$i
done

# update configuration Tunning / auth / debug  off 


echo "copy and update ceph.conf remove auto and debug  "  







