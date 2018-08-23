#!/bin/sh

NVME=nvme0n1
NVME=nvme1n1

sgdisk -Z --clear -g /dev/$NVME
sgdisk -Z --clear -g /dev/$NVME

parted -s -a optimal /dev/$NVME mkpart primary 0G 350G

mkfs.xfs /dev/$NVMEp1
wipefs -a /dev/$NVMEp1

salt "node1" ceph_sles.make_bcache /dev/nvme01p1 /dev/sdb /dev/sdc /dev/sdd /dev/sde /dev/sdf /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl

# salt "node1" ceph_sles.make_bcache /dev/nvme01p1 /dev/sdm /dev/sdn /dev/sdo /dev/sdp /dev/sdq /dev/sdr /dev/sds /dev/sdt /dev/sdu /dev/sdv /dev/sdw
