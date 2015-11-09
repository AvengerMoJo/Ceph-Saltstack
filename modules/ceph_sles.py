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

def keygen(): 
	'''
	Create ssh key from the admin node Admin node should be the one running
	ceph-deploy in the future

	CLI Example:

	..  code-block:: bash
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

        ..  code-block:: bash
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

def ceph_new( *node_names ):
	'''
        Create new ceph cluster configuration by running ceph-deploy new, mon
	create-initial, admin 

        CLI Example:

        ..  code-block:: bash
                salt 'node1' ceph_sles.ceph_new node1 node2 node3 ....
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

def ceph_push( *node_names ):
	'''
        Send cluster configuration file from to all needed nodes

        CLI Example:

        ..  code-block:: bash
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

        ..  code-block:: bash
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

        ..  code-block:: bash
                salt 'node1' ceph_sles.bench_disk
        '''
	dev_list = '' 
	for dev in disk_dev:
		if __salt__['file.is_blkdev'](dev):
			dev_list = dev_list + dev + ' '
	result = __salt__['cmd.run']('/sbin/hdparm -T ' + dev_list , output_loglevel='debug')
	return result


def bench_network( master_node, *client_node ):
	'''
	Get all the disk device from nodes

	CLI Example:

	..  code-block:: bash
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


def clean_disk_partition( *disk_dev ):
	'''
	Remove disk partition table 

	CLI Example:

	..  code-block:: bash
		salt 'node1' ceph_sles.clean_disk_partition /dev/sdb /dev/sdb /dev/sdc ...
	'''
	node_name = socket.gethostname()
	disk_zap = dev_list = '' 
	for dev in disk_dev:
		if __salt__['file.is_blkdev'](dev):
			disk_zap += __salt__['cmd.run']('ceph-deploy disk zap ' + node_name + ':' + dev , output_loglevel='debug', cwd='/etc/ceph' )
	return disk_zap

def _parted_start( dev ):
	start = __salt__['cmd.run']('parted -m -s ' + dev +
		' unit s print free | grep free  | sort -t : -k 4n -k 2n  | tail -n 1 | cut -f 2 -d ":" | cut -f 1 -d "s" ', output_loglevel='debug' )
	return int(start)

def _disk_sector_size( dev ):
	# lsblk /dev/sda -o PHY-SEC,LOG-SEC
	# /sys/block/sda/queue/hw_sector_size
	size = __salt__['cmd.run']('lsblk ' + dev + ' -o LOG-SEC | head -n 2 | tail -n 1', output_loglevel='debug' )
	return int(size)

def _disk_last_part( dev ):
	part = __salt__['cmd.run']('parted ' + dev + ' print -m -s | tail -1 | cut -f 1 -d ":"', output_loglevel='debug' )
	if part.isdigit():
		return int(part)
	else:
		return False

def _disk_remove_last_part( dev ):
	part = _disk_last_part( dev )
	if part:
		remove_part = __salt__['cmd.run']('parted ' + dev + ' rm ' + str(part), output_loglevel='debug' )

def _disk_new_part( dev, part_size ):

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
		part_free = __salt__['cmd.run']('parted -a optimal -m -s ' + dev + ' unit s -- mkpart primary ' + str(start) + ' ' + str(end), output_loglevel='debug' )

def _disk_part_label( dev ):
	disk_id = __salt__['cmd.run']('/usr/lib/udev/ata_id ' + dev, output_loglevel='debug')
	return 'ata-' + disk_id + '-part'

def _disk_format_xfs( dev_part ):
	format_part = __salt__['cmd.run']('/usr/sbin/mkfs.xfs ' + dev_part , output_loglevel='debug')
	return format_part

def _fstab_update_part( part, path ):
	cp_fstab= __salt__['cmd.run']('cp /etc/fstab /etc/fstab.bak', output_loglevel='debug' )
	remove_part = __salt__['cmd.run']('grep -v ' + part + ' /etc/fstab.bak > /etc/fstab', output_loglevel='debug' )
	add_part = __salt__['cmd.run']('echo "/dev/disk/by-id/' + part + ' ' + path + ' xfs	rw,defaults,noexec,nodev,noatime,nodiratime,nobarrier 0 0  ">> /etc/fstab', output_loglevel='debug' )

def prep_osd_journal( partition_dev, part_size ):
	'''
	Create disk partition for future OSD jounral, it will be using the a new partition
	with the size specified to create partition to place future journal

	CLI Example:

	..  code-block:: bash
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

