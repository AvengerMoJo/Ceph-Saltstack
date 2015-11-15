# -*- coding: utf-8 -*-
'''
 AvengerMoJo (alau@suse.com) 
 A SaltStack interface for Ceph Deploy and Configuration

'''

# Import Python libs for logging
import logging
import os
import re
import socket
import time
import getopt

# Import salt library for running remote commnad
import salt.modules.cmdmod as salt_cmd
import salt.utils as salt_utils 
# import salt.modules.pkg as salt_pkg


log = logging.getLogger(__name__)
log.debug('Loading ssh key from admin node')


__virtual_name__ = 'ceph_sles'

def __virtual__():
	if __grains__.get('os',False) != 'SLES':
		return False
	#if pkg.version('ceph',False) < '0.94':
	if not salt_utils.which('ssh-keygen') :
		log.info('Error ssh-keygen package not find, need to be installed' )
		return False
	if not salt_utils.which('ssh-keyscan') :
		log.info('Error ssh-keyscan package not find, need to be installed' )
		return False
	if not salt_utils.which('sshpass') :
		log.info('Error sshpass package not find, need to be installed' )
		return False
	if not salt_utils.which('lsblk') :
		log.info('Error lsblk package not find, need to be installed' )
		return False
	if not salt_utils.which('iperf3') :
		log.info('Error iperf3 package not find, need to be installed' )
		return False
	return __virtual_name__
	# return 'ceph_sles'

def _parted_start( dev ):
	'''
	get disk partition free sector start number 
	'''
	start = __salt__['cmd.run']('parted -m -s ' + dev +
		' unit s print free | grep free  | sort -t : -k 4n -k 2n  | tail -n 1 | cut -f 2 -d ":" | cut -f 1 -d "s" ', output_loglevel='debug' )
	return int(start)

def _disk_sector_size( dev ):
	'''
	get disk sector size 
	'''
	# lsblk /dev/sda -o PHY-SEC,LOG-SEC
	# /sys/block/sda/queue/hw_sector_size
	size = __salt__['cmd.run']('lsblk ' + dev + ' -o LOG-SEC | head -n 2 | tail -n 1', output_loglevel='debug' )
	return int(size)

def _disk_last_part( dev ):
	'''
	get disk highest partition number 
	'''
	part = __salt__['cmd.run']('parted ' + dev + ' print -m -s | tail -1 | cut -f 1 -d ":"', output_loglevel='debug' )
	if part.isdigit():
		return int(part)
	else:
		return False

def _disk_remove_last_part( dev ):
	'''
	remove the highest partition
	'''
	part = _disk_last_part( dev )
	if part:
		remove_part = __salt__['cmd.run']('parted ' + dev + ' rm ' + str(part), output_loglevel='debug' )

def _disk_new_part( dev, part_size ):
	'''
	create a partition in the top partition with size in MB or GB 
	'''
	size_string = part_size 
	sector_size = _disk_sector_size( dev )
	unit_size = 1024 * 1024
	temp = "" 

	start = _parted_start( dev )
	if start < 2048:
		start = 2048
	elif start % sector_size != 0:
		start = ((start / sector_size) + 1) * sector_size
	
	for size in str(size_string):
		if size.isdigit():
			temp += size
		elif size == 'G':
			unit_size = 1024 * unit_size
	end = (int(temp) * unit_size / sector_size) + start -1

	if start > 0:
		__salt__['cmd.run']('parted -a optimal -m -s ' + dev + ' unit s -- mkpart primary ' + str(start) + ' ' + str(end), output_loglevel='debug' )
		__salt__['cmd.run']('partprobe ' + dev, output_loglevel='debug' )

def _disk_part_label( dev ):
	'''
	get partition name for mount dev id in suse udev default fstab format
	'''
	disk_id = __salt__['cmd.run']('/usr/lib/udev/ata_id ' + dev, output_loglevel='debug')
	return 'ata-' + disk_id + '-part'

def _disk_format_xfs( dev_part ):
	'''
	format partition to xfs format
	'''
	format_part = __salt__['cmd.run']('/usr/sbin/mkfs.xfs -f ' + dev_part , output_loglevel='debug')
	return format_part

def _fstab_remove_part( part ):
	'''
	remove partition mount point from fstab
	'''
	cp_fstab= __salt__['cmd.run']('cp /etc/fstab /etc/fstab.bak', output_loglevel='debug' )
	remove_part = __salt__['cmd.run']('grep -v ' + part + ' /etc/fstab.bak > /etc/fstab', output_loglevel='debug' )

def _fstab_add_part( part, path ):
	'''
	put in the new partition and mount point into fstab
	'''
	_fstab_remove_part( part )
	add_part = __salt__['cmd.run']('echo "/dev/disk/by-id/' + part + ' ' + path +
	' xfs	rw,defaults,noexec,nodev,noatime,nodiratime,nobarrier 0 0  ">> /etc/fstab', output_loglevel='debug' )

def _prep_activate_osd( node, part, journal ):
	prep = __salt__['cmd.run']('ceph-deploy osd prepare '+ node + ':' + part + ':' + journal, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	activate = __salt__['cmd.run']('ceph-deploy osd activate '+ node + ':' + part, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return prep+activate

def keygen(): 
	'''
	Create ssh key from the admin node Admin node should be the one running
	ceph-deploy in the future

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.keygen
	'''

	out_log  = __salt__['cmd.run']('ssh-keygen -b 2048 -t rsa -f /home/ceph/.ssh/id_rsa -q -N ""', output_loglevel='debug', runas='ceph' )
	# sshkey = salt_cmd.run('ssh-keygen', output_loglevel='debug', runas='ceph')
	return out_log


def send_key( *node_names ):
	'''
        Send ssh key from the admin node to the rest of the node allow 
        ceph-deploy in the future

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.send_key node1 node2 node3 ....

        '''
	out_log = []
	for node in node_names :
		out_log.append( __salt__['cmd.run']('ssh-keygen -R '+ socket.gethostbyname(node), output_loglevel='debug', runas='ceph' ))
		out_log.append( __salt__['cmd.run']('ssh-keygen -R '+ node, output_loglevel='debug', runas='ceph' ))
		out_log.append( __salt__['cmd.run']('ssh-keyscan '+ node +' >> ~/.ssh/known_hosts'  , output_loglevel='debug', runas='ceph' ))
		# assume the kiwi image predefine user ceph with password suse1234
		out_log.append( __salt__['cmd.run']('sshpass -p "suse1234" ssh-copy-id ceph@'+node , output_loglevel='debug', runas='ceph' ))
	return out_log

def new_mon( *node_names ):
	'''
        Create new ceph cluster configuration by running ceph-deploy new, mon
	create-initial, admin 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.new_mon node1 node2 node3 ....
	'''
	node_list = ''
	for node in node_names :
		node_list = node_list + node + ' '
	
	if not os.path.exists( '/home/ceph/cluster_config' ): 
		mkdir_log  = __salt__['cmd.run']('mkdir -p /home/ceph/.ceph_sles_cluster_config', output_loglevel='debug', runas='ceph' )

	if not salt_utils.istextfile( '/home/ceph/.ceph_sles_cluster_config/ceph.conf' ):
		deploy_new_log  = __salt__['cmd.run']('ceph-deploy new '+ node_list  , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )

	out_log  = __salt__['cmd.run']('ceph-deploy --overwrite-conf mon create-initial' , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return mkdir_log + deploy_new_log + out_log

def push_conf( *node_names ):
	'''
        Send cluster configuration file from to all needed nodes

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.ceph_push node1 node2 node3 ....
	'''
	node_list = ''
	for node in node_names:
		node_list = node_list + node + ' '
	out_log  = __salt__['cmd.run']('ceph-deploy --overwrite-conf admin '+ node_list  , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return out_log

def get_disk_info():
	'''
	Get all the disk device from nodes 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.get_disk_info 
        '''
	result = __salt__['cmd.run']('lsblk | grep ^sd*', output_loglevel='debug')
	dev_names = re.findall( r'(?P<disk_name>sd.).*', result )
	hdd_list = []
	ssd_list = []
	for dev_name in dev_names:
		cat_out = __salt__['cmd.run']('cat /sys/block/'+ dev_name +'/queue/rotational', output_loglevel='debug')
		if cat_out[0] is "1":
			hdd_list.append( dev_name )
			result = re.sub(r'('+dev_name+'.*)disk', r'\1hdd disk', result) 
		else:
			ssd_list.append( dev_name )
			result = re.sub(r'('+dev_name+'.*)disk', r'\1ssd disk', result) 
	out_log = result
	#out_log = out_log + "\nhdd: \n" + ",".join(hdd_list)
	#out_log = out_log + "\nssd: \n" + ",".join(ssd_list)
	return out_log

def bench_disk( *disk_dev ):
	'''
	Get disk device direct read performance

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.bench_disk /dev/sda /dev/sdb ...
        '''
	dev_list = '' 
	for dev in disk_dev:
		if __salt__['file.is_blkdev'](dev):
			dev_list = dev_list + dev + ' '
	result = __salt__['cmd.run']('/sbin/hdparm -t ' + dev_list , output_loglevel='debug')
	return result


def bench_network( master_node, *client_node ):
	'''
	Get all the disk device from nodes

	CLI Example:

	.. code-block:: bash
	salt 'node*' ceph_sles.bench_network admin_node node1 node2 node3 ... 
	'''

	iperf_out = False
	node_name = socket.gethostname()

	if node_name == master_node:
		iperf_out = __salt__['state.sls']('iperf')
	else:
		for node in client_node:
			time.sleep(15) # delays for 5 seconds
			if node == node_name:
				iperf_out = __salt__['cmd.run']('/usr/bin/iperf3 -c ' + master_node + ' -d' , output_loglevel='debug')
				break
	return iperf_out 


def clean_disk_partition( nodelist=None, partlist=None):
	'''
	Remove disk partition table 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.clean_disk_partition "node1,node2,node3" "/dev/sdb,/dev/sdc,/dev/sde"
	'''
	node_name = socket.gethostname()
	node_list = nodelist.split(",")
	part_list = partlist.split(",")
	disk_zap = ""

	for node in node_list:
		# if __salt__['file.is_blkdev'](dev):
		for part in part_list:
			disk_zap += __salt__['cmd.run']('ceph-deploy disk zap ' + node +
			 ':' + part , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return disk_zap

def prep_osd_journal( partition_dev, part_size ):
	'''
	Create disk partition for future OSD jounral, it will be using the a new partition
	with the size specified to create partition to place future journal

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.prep_osd_journal /dev/sda 40G 

	'''
	journal_path = '/var/lib/ceph/osd/journal'
	_disk_new_part( partition_dev, part_size )
	if not os.path.exists( journal_path ):
		mkdir_log  = __salt__['cmd.run']('mkdir -p ' + journal_path, output_loglevel='debug' )
	new_part_num = _disk_last_part( partition_dev )
	if not new_part_num:
		return False
	else:
		_disk_format_xfs( partition_dev + str(new_part_num) )
		new_part_label = _disk_part_label( partition_dev ) + str(new_part_num)
		_fstab_update_part( new_part_label, journal_path ) 

	new_part_mount = __salt__['cmd.run']('mount '+ journal_path, output_loglevel='debug' )

	new_part_mount += "\n\n"
	new_part_mount += __salt__['cmd.run']('parted ' + partition_dev + ' unit s print free', output_loglevel='debug' )
	new_part_mount += "\n\n"
	new_part_mount += __salt__['cmd.run']('mount', output_loglevel='debug' )
	return new_part_mount

def prep_osd( nodelist=None, partlist=None):
	'''
	Prepare all the osd and activate them 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.prep_osd "node1,node2,node3" "/dev/sda5,/dev/sdb,/dev/sdc,/dev/sdd,/dev/sde"

	'''
	journal_path = '/var/lib/ceph/osd/journal/osd-'
	result = ""
	osd_num = 0
	node_list = nodelist.split(",")
	part_list = partlist.split(",")

	for node in node_list:
		for part in part_list:
			result += _prep_activate_osd( node, part, journal_path+str(osd_num))
			osd_num += 1
	return result

def _list_osd_files():
	'''
	return line seperated list of osd directory in /var/lib/ceph/osd
	'''
	osd_path = '/var/lib/ceph/osd/'
	possible_osd = __salt__['cmd.run']('ls '+ osd_path + ' | grep ceph' , output_loglevel='debug')
	return possible_osd

def _umount_path( path ):
	'''
	umount the mount point by the path 
	'''
	umount = __salt__['cmd.run']('umount '+ path, output_loglevel='debug')
	return umount

def _remove_journal( osd_num ):
	'''
	clean up journal file after osd removed
	'''
	if os.path.exists( '/var/lib/ceph/osd/journal/osd-' + str(osd_num)):
		remove_journal = __salt__['cmd.run']('rm -rf /var/lib/ceph/osd/ceph-' + str(remove_osd), output_loglevel='debug')
		return True
	return False

def list_osd():
	'''
	List out all the osd is mounted and running 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.list_osd 
	'''
	osd_list = _list_osd_files().split("\n")
	mounted_osd = ""
	file_list = ""

	for osd in osd_list:
		if osd:
			mounted_osd += "\n" + __salt__['cmd.run']('mount | grep ' + osd + '| cut -f 3 -d " "' , output_loglevel='debug')
			file_list += "\n" + osd
	return "Possible OSD is not clean in /var/lib/ceph/osd/ :\n" + file_list + "\n\nCurrently mounted osd :\n" + mounted_osd


def clean_osd( *osd_num ):
	'''
	Umount the osd mount point and clean up the host osd leave over files

	CLI Example:

	.. code-block:: bash
	salt 'node*' ceph_sles.clean_osd 0 1 2 3 
	'''
	clean_log = ""
	for remove_osd in osd_num:
		for ceph_path in _list_osd_files().split("\n"):
			mounted = __salt__['cmd.run']('mount | grep "' + ceph_path + '"| grep ceph-' + str(remove_osd) + '| cut -f 3 -d " "', output_loglevel='debug')
			if mounted:
				clean_log += 'umount ' + mounted
				_umount_path( mounted )
			elif os.path.exists( '/var/lib/ceph/osd/ceph-' + str(remove_osd)):
				clean_log += 'remove /var/lib/ceph/osd/ceph-' + str(remove_osd)
				__salt__['cmd.run']('rm -rf /var/lib/ceph/osd/ceph-' + str(remove_osd), output_loglevel='debug')
		clean_log += 'remove journal ' + _remove_journal( remove_osd )
	return clean_log

def remove_osd( *osd_num ):
	'''
	Remove osd from the cluster 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.remove_osd 0 1 2 3 

	'''
	remove = "" 
	for osd in osd_num:
		remove += __salt__['cmd.run']('ceph osd down osd.'+ str(osd), output_loglevel='debug', cwd='/etc/ceph' )
		remove += __salt__['cmd.run']('ceph osd crush remove osd.'+ str(osd), output_loglevel='debug', cwd='/etc/ceph' )
		remove += __salt__['cmd.run']('ceph auth del osd.'+ str(osd), output_loglevel='debug', cwd='/etc/ceph' )
		remove += __salt__['cmd.run']('ceph osd rm '+ str(osd), output_loglevel='debug', cwd='/etc/ceph' )

	return remove

