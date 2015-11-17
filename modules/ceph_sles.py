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
import json
import fileinput

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

def _cpu_info():
	'''
	cat /proc/cpuinfo Profile record for the cluster information
	'''
	info = __salt__['cmd.run']('cat /proc/cpuinfo', output_loglevel='debug' )
	return "\n/proc/cpuinfo:\n" + info

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

def _ip_info():
	'''
	ip -d addr  Profile record for the cluster information
	'''
	info = __salt__['cmd.run']('ip -d link', output_loglevel='debug' )
	info += __salt__['cmd.run']('ip -d addr', output_loglevel='debug' )
	return "\nip -d a & ip -d l:\n" + info

def _list_osd_files():
	'''
	return line seperated list of osd directory in /var/lib/ceph/osd
	'''
	osd_path = '/var/lib/ceph/osd/'
	possible_osd = __salt__['cmd.run']('ls '+ osd_path + ' | grep ceph' , output_loglevel='debug')
	return possible_osd

def _lsblk_list_all():
	'''
	lsblk -a -O Profile record for the cluster information
	'''
	info = __salt__['cmd.run']('lsblk -a -O', output_loglevel='debug' )
	return "\nlsblk -a -O:\n" + info

def _lspci():
	'''
	lspci Profile record for the cluster information
	'''
	info = __salt__['cmd.run']('lspci ', output_loglevel='debug' )
	return "\nlspci:\n" + info

def _parted_start( dev ):
	'''
	get disk partition free sector start number 
	'''
	start = __salt__['cmd.run']('parted -m -s ' + dev +
		' unit s print free | grep free  | sort -t : -k 4n -k 2n  | tail -n 1 | cut -f 2 -d ":" | cut -f 1 -d "s" ', output_loglevel='debug' )
	return int(start)

def _prep_activate_osd( node, part, journal ):
	prep = __salt__['cmd.run']('ceph-deploy osd prepare '+ node + ':' + part + ':' + journal, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	activate = __salt__['cmd.run']('ceph-deploy osd activate '+ node + ':' + part, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return prep+activate

def _remove_journal( osd_num ):
	'''
	clean up journal file after osd removed
	'''
	if os.path.exists( '/var/lib/ceph/osd/journal/osd-' + str(osd_num)):
		remove_journal = __salt__['cmd.run']('rm -rf /var/lib/ceph/osd/ceph-' + str(remove_osd), output_loglevel='debug')
		return True
	return False

def _scsi_info():
	'''
	cat /proc/scsi/scsi disk profile record for the cluster information
	'''
	info = __salt__['cmd.run']('cat /proc/scsi/scsi', output_loglevel='debug' )
	return "\n/proc/scsi/scsi:\n" + info

def _umount_path( path ):
	'''
	umount the mount point by the path 
	'''
	umount = __salt__['cmd.run']('umount '+ path, output_loglevel='debug')
	return umount

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
	
	if not os.path.exists( '/home/ceph/.ceph_sles_cluster_config' ): 
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

def disk_info():
	'''
	Get all the disk device from nodes 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.disk_info 
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

	if osd_list[0] == "" :
		return "There is file in osd default path, assume no OSD in this node." 
	for osd in osd_list:
		if osd:
			mounted_osd += "\n" + __salt__['cmd.run']('mount | grep ' + osd + '| cut -f 3 -d " "' , output_loglevel='debug')
			mounted_osd += "\t" + __salt__['cmd.run']('mount | grep ' + osd + '| cut -f 1 -d " "' , output_loglevel='debug')
			file_list += "\n" + osd
	return "Possible OSD is not clean in /var/lib/ceph/osd/ :\n" + file_list + "\n\nCurrently mounted osd :\t Mount point:\n" + mounted_osd


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


def profile_node():
	'''
	Run a list of private function to get hardware information from the cluster node

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.profile_node

	'''
	output = _lsblk_list_all()
	output += _scsi_info()
	output += _ip_info()
	output += _lspci()
	output += _cpu_info()
	return output

def _crushmap_disktype_output( disk_type, next_id, osd_weight_total, osd_weight_line ):
	'''
	Run the command from master-admin node to get all disk info and output
	crushmap output with disktype being listed
	'''
	output = "disktype osd_" + disk_type + " {\n" 
	output += "\tid " + str(next_id) + " # do not change unnecessarily\n"
	output += "\t# weight " + str( osd_weight_total ) + "\n" 
	output += "\talg straw\n\thash 0\n" 
	output += osd_weight_line + "}"
	return output

def _crushmap_root_disktype_output( disk_type, next_id, osd_weight_total ):
	output = "root root_" + disk_type + " {\n" 
	output += "\tid " + str(next_id) + " # do not change unnecessarily\n"
	output += "\t# weight " + str( osd_weight_total ) + "\n" 
	output += "\talg straw\n\thash 0\n" 
	output += "\titem osd_" + disk_type + " weight " + str(osd_weight_total)
	output += "\n}"
	return output

def _osd_tree_obj():
	tree_view_json =  __salt__['cmd.run']('ceph osd tree --format json | grep {', output_loglevel='debug', cwd='/etc/ceph', runas='ceph' )
	tree_view = json.loads( tree_view_json )
	return tree_view

def _osd_tree_next_id( osd_tree_json_object ):
	'''
	Get the next id from the osd tree for crushmap update
	it should be the next -1 id form the current lowest id 
	'''
	next_id = 0 
	for child in osd_tree_json_object['nodes']:
		if next_id > child['id']:
			next_id = int( child['id'] )
	next_id -= 1 
	return next_id

def _osd_tree_osd_weight( osd_tree_json_object, osd_num ):
	'''
	Get the osd weight from the osd tree json object for crushmap update by the osd.num
	it should be the next -1 id form the current lowest id 
	'''
	osd_weight = 0.0000
	for child in osd_tree_json_object['nodes']:
		if child['name'] == "osd." + str(osd_num):
			osd_weight = child['crush_weight']
	return osd_weight

def _parse_disktype( disk_info_result, disktype ):
	'''
	Feed disk_info result into the function and extract node disktype line by line
	'''
	dev_list = re.findall( r'\s+(\w+)\s+\d+:\d+\s+[0-9]\s+\d+\.\d[G|T]\s+[0|1]\s'+disktype, disk_info_result )
	return dev_list

def _parse_list_osd( list_osd_result, dev_name ):
	'''
	Feed list_osd result into the function and extract osd number line by line
	'''
	dev_list = re.findall( r'/var/lib/ceph/osd/ceph-(\d+)\s+.*'+dev_name+'.*', list_osd_result)
	return dev_list

def crushmap_add_hdd_ssd_tree( *node_names ):
	'''
	Run the command from master-admin node to get all ssd osd in the cluster 
	and then put that into a crushmap format. 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.crushmap_add_hdd_ssd_tree node1 node2 node3 

	'''
	output = ""
	ssd_osd_weight_output = ""
	ssd_osd_weight_total = 0.000
	hdd_osd_weight_output = ""
	hdd_osd_weight_total = 0.000

	tree_view_json = _osd_tree_obj()
	next_id = _osd_tree_next_id( tree_view_json ) 

	for node in node_names:
		disk_info_result =  __salt__['cmd.run']('salt "' + node + '" ceph_sles.disk_info', output_loglevel='debug' )
		list_osd_result =  __salt__['cmd.run']('salt "' + node + '" ceph_sles.list_osd', output_loglevel='debug' )
		ssd_disks =  _parse_disktype( disk_info_result, 'ssd' )
		if ssd_disks is not None:
			for ssd_dev in ssd_disks:
				osd_num_list = _parse_list_osd( list_osd_result, ssd_dev )
				if osd_num_list is not None:	
					for osd_num in osd_num_list:
						weight  = _osd_tree_osd_weight( tree_view_json, osd_num ) 
						ssd_osd_weight_total += weight
						ssd_osd_weight_output += "\titem osd."+ str(osd_num) + " weight " + str( weight ) + "\n"
		hdd_disks =  _parse_disktype( disk_info_result, 'hdd' )
		if hdd_disks is not None:
			for hdd_dev in hdd_disks:
				osd_num_list = _parse_list_osd( list_osd_result, hdd_dev )
				if osd_num_list is not None:	
					for osd_num in osd_num_list:
						#output += "osdnum :"+ osd_num+"\n"
						weight  = _osd_tree_osd_weight( tree_view_json, osd_num ) 
						hdd_osd_weight_total += weight
						hdd_osd_weight_output += "\titem osd."+ str(osd_num) + " weight " + str( weight ) + "\n"
						# output += " hdd=" + hdd_dev + " osd=osd." + str(osd_num) 
	crushmap_ssd_out = _crushmap_disktype_output( 'ssd', next_id, ssd_osd_weight_total, ssd_osd_weight_output )
	output += crushmap_ssd_out 
	output += "\n\n"
	crushmap_hdd_out = _crushmap_disktype_output( 'hdd', next_id-1, hdd_osd_weight_total, hdd_osd_weight_output )
	output += crushmap_hdd_out
	output += "\n\n"
	crushmap_root_ssd_out = _crushmap_root_disktype_output( 'ssd', next_id-2, ssd_osd_weight_total )
	output += crushmap_root_ssd_out 
	output += "\n\n"
	crushmap_root_hdd_out = _crushmap_root_disktype_output( 'hdd', next_id-3, hdd_osd_weight_total )
	output += crushmap_root_hdd_out 
	output += "\n\n"

	return output

def _prepare_crushmap():
	'''
	Create a directory for hold current crushmap configuration and modify later
	'''
	crushmap_path = '/home/ceph/.ceph_sles_cluster_config/crushmap'
	orig_bin_map = 'orig_crushmap.bin'
	orig_txt_map = 'orig_crushmap.txt'
	new_txt_map = 'new_crushmap.txt'

	if not os.path.exists( crushmap_path ):
		mkdir_log  = __salt__['cmd.run']('mkdir -p ' + crushmap_path, output_loglevel='debug', runas='ceph' )

	prep = __salt__['cmd.run']('ceph osd getcrushmap -o ' + orig_bin_map, output_loglevel='debug', runas='ceph', cwd=crushmap_path )
	prep += __salt__['cmd.run']('crushtool -d ' + orig_bin_map + ' -o ' + orig_txt_map , output_loglevel='debug', runas='ceph', cwd=crushmap_path )
	prep += __salt__['cmd.run']('cp ' + orig_txt_map + ' ' + new_txt_map  , output_loglevel='debug', runas='ceph', cwd=crushmap_path )

	return prep

def _read_crushmap_begin_section( begin_line, end_line ):
	'''
	Read the new_crushmap.txt and get the first section 
	from line e.g. "# begin crush map" to "# devices"
	'''
	crushmap_path = '/home/ceph/.ceph_sles_cluster_config/crushmap'
	new_txt_map = 'new_crushmap.txt'
	output = ""
	in_section = False

	for line in fileinput.input( crushmap_path + '/' + new_txt_map ):
		if line.startswith( begin_line ):
			in_section = True
		if line.startswith( end_line ):
			in_section = False
		if in_section:
			output += line

	return output

def _update_crushmap():
	'''
	Compile and install the new crushmap into the cluster 
	'''
	crushmap_path = '/home/ceph/.ceph_sles_cluster_config/crushmap'
	new_txt_map = 'new_crushmap.txt'
	new_bin_map = 'new_crushmap.bin'

	prep = __salt__['cmd.run']('crushtool -c ' + new_txt_map + ' -o ' + new_bin_map, output_loglevel='debug', runas='ceph', cwd=crushmap_path )
	prep += __salt__['cmd.run']('ceph osd setcrushmap -i ' + new_bin_map, output_loglevel='debug', runas='ceph', cwd=crushmap_path )

	return prep


def _crushmap_add_disktype():
	'''
	Update types section as following : 
	'''
	new_type = '# types\n'
	new_type += 'type 0 osd\n'
	new_type += 'type 1 disktype\n'
	new_type += 'type 2 host\n'
	new_type += 'type 3 chassis\n'
	new_type += 'type 4 rack\n'
	new_type += 'type 5 row\n'
	new_type += 'type 6 pdu\n'
	new_type += 'type 7 pod\n'
	new_type += 'type 8 room\n'
	new_type += 'type 9 datacenter\n'
	new_type += 'type 10 region\n'
	new_type += 'type 11 root\n\n'
	return new_type

def _crushmap_add_ssd_hdd_ruleset( rule_type, next_ruleset_id, min_size, max_size ):
	'''
	Add the following ruleset for pick only ssd or hdd for data placement
	'''
	ssd_ruleset = 'rule ssd_' + rule_type + ' {\n'
	ssd_ruleset += '\truleset ' + str( next_ruleset_id ) + '\n'
	ssd_ruleset += '\ttype ' + rule_type + '\n'
	ssd_ruleset += '\tmin_size ' + str( min_size ) + '\n'
	ssd_ruleset += '\tmax_size ' + str( max_size ) + '\n'
	ssd_ruleset += '\tstep take root_ssd\n'
	ssd_ruleset += '\tstep chooseleaf firstn 0 type osd\n'
	ssd_ruleset += '\tstep emit\n'
	ssd_ruleset += '}\n'

	hdd_ruleset = 'rule hdd_' + rule_type + ' {\n'
	hdd_ruleset += '\truleset ' + str( next_ruleset_id+1 )+ '\n'
	hdd_ruleset += '\ttype ' + rule_type + '\n'
	hdd_ruleset += '\tmin_size ' + str( min_size ) + '\n'
	hdd_ruleset += '\tmax_size ' + str( max_size ) + '\n'
	hdd_ruleset += '\tstep take root_hdd\n'
	hdd_ruleset += '\tstep chooseleaf firstn 0 type osd\n'
	hdd_ruleset += '\tstep emit\n'
	hdd_ruleset += '}\n'
	
	return ssd_ruleset + hdd_ruleset

def _read_ruleset_next_id( all_ruleset ):
	'''
	Return the max + 1 ruleset id form the crushmap line buffer 
	'''
	next_id = 0
	all_id = re.findall( r'ruleset (?P<id>\d).*', all_ruleset )
	for rule_id in all_id:
		if int(rule_id) > next_id:
			next_id = int( rule_id ) 
	return next_id + 1

def crushmap_update_disktype_ssd_hdd( *node_names ):
	'''
	Run the command from master-admin node
	1) Prepare crushmap in /home/ceph/.ceph_sles_cluster_config/crushmap
	2) Add disktype to default crushmap
	3) Find all node ssd and hdd and group them into root_sdd and root_hdd 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.crushmap_update_disktype_ssd_hdd node1 node2 node3 

	'''
	crushmap_path = '/home/ceph/.ceph_sles_cluster_config/crushmap'
	new_txt_map = 'new_crushmap.txt'

	begin_line = '# begin crush map'
	type_line = '# types'
	bucket_line = '# buckets'
	rule_line = '# rules'
	end_line = '# end crush map'
	
	# prepare the file of crushmap from the running cluster 
	_prepare_crushmap()
	# get the first section of the crushmap text file 
	before_type = _read_crushmap_begin_section( begin_line, type_line )
	# add the disktype into the crushmap type list
	new_type = _crushmap_add_disktype()
	# get the bucket section until the ruleset
	bucket_list = _read_crushmap_begin_section( bucket_line, rule_line )
	# add the pure ssd and pure hdd bucket 
	bucket_ssd_hdd = crushmap_add_hdd_ssd_tree( *node_names )
	# get the ruleset of the curshmap
	ruleset_list = _read_crushmap_begin_section( rule_line, end_line )
	# get the highest number of ruleset id + 1 
	next_ruleset_id = _read_ruleset_next_id( ruleset_list )
	# let's fix this later, I'm sure there is better way to setup min and max 
	min_size = 1
	max_size = 3 
	# add the ssd and hdd replicated ruleset 
	ruleset_list += _crushmap_add_ssd_hdd_ruleset( 'replicated', next_ruleset_id, min_size, max_size )
	ruleset_list += '\n' + end_line + '\n'

	new_crushmap = before_type + new_type + bucket_list + bucket_ssd_hdd + ruleset_list
	new_crushmap_file = open( crushmap_path + '/' + new_txt_map, "w" ) 
	new_crushmap_file.write( new_crushmap )
	new_crushmap_file.close()

	return _update_crushmap()
