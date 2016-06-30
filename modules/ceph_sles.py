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
import StringIO

# Import salt library for running remote commnad
import salt.modules.cmdmod as salt_cmd
import salt.utils as salt_utils 
# import salt.modules.pkg as salt_pkg


log = logging.getLogger(__name__)
log.debug('Loading ssh key from admin node')


__virtual_name__ = 'ceph_sles'

def __virtual__():
	#if __grains__.get('os',False) != 'SLES':
		#return False
	#if pkg.version('ceph',False) < '0.94':
	#if not salt_utils.which('ssh-keygen') :
	#	log.info('Error ssh-keygen package not find, need to be installed' )
	#	return False
	#if not salt_utils.which('ssh-keyscan') :
	#	log.info('Error ssh-keyscan package not find, need to be installed' )
	#	return False
	#if not salt_utils.which('sshpass') :
	#	log.info('Error sshpass package not find, need to be installed' )
	#	return False
	if not salt_utils.which('lsblk') :
		log.info('Error lsblk package not find, need to be installed' )
		return False
	if not salt_utils.which('iperf3') :
		log.info('Error iperf3 package not find, need to be installed' )
		return False
	return __virtual_name__
	# return 'ceph_sles'

def _bench_prep():
	'''
	Prepare bench report gathering directory 
	'''
	bench_path = '/home/ceph/.ceph_sles_bench_report'
	if not os.path.exists( bench_path ):
		mkdir_log = __salt__['cmd.run']('mkdir -p ' + bench_path, output_loglevel='debug', runas='ceph' )
		return mkdir_log 
	else:
		return True

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
	possible_osd = __salt__['cmd.shell']('ls '+ osd_path + ' | grep ceph' , output_loglevel='debug')
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
	start = __salt__['cmd.shell']('parted -m -s ' + dev +
		' unit s print free | grep free  | sort -t : -k 4n -k 2n  | tail -n 1 | cut -f 2 -d ":" | cut -f 1 -d "s" ', output_loglevel='debug' )
	return int(start)

def prep_activate_osd_local(part, journal=None):
	node = socket.gethostname()
	return _prep_activate_osd( node, part, journal )

def _prep_activate_osd( node, part, journal=None ):
	ceph_conf_file = '/etc/ceph/ceph.conf'
	osd_path = '/var/lib/ceph/osd'

	uuid = __salt__['cmd.run']('uuidgen', env={'HOME':'/root'} )
	# new_osd_id = __salt__['cmd.run']('ceph osd create ' + uuid, output_loglevel='debug', env={'HOME':'/root'} )

	output = 'Node = ' + node + '\n'
	output += 'Gen uuid = ' + uuid + '\n'
	output += 'Journal file = ' + str(journal) + '\n'


	fsid = ''
	for line in fileinput.input( ceph_conf_file ):
		if line.startswith( 'fsid' ):
			fsid = line.split('=')[1].strip()

	# osd_name_dir = osd_path + '/ceph-' + new_osd_id
	 #output += __salt__['cmd.run']('mkdir -p ' + osd_name_dir, output_loglevel='debug' ) + '\n'

	output += 'FSID = ' + fsid + '\n'

	# new_partition = __salt__['cmd.run']('parted ' + part + ' mkpart xfs 2048s 100%', output_loglevel='debug' ) + '\n'
	# prep = __salt__['cmd.run']('ceph-disk prepare --cluster ceph --cluster-uuid '+ fsid + ' --fs-type xfs --data-dev ' + part + ' ' + journal, output_loglevel='debug', env={'HOME':'/root'} )
	if journal:
		prep = __salt__['cmd.run']('ceph-disk prepare --cluster ceph --cluster-uuid '+ fsid + ' --fs-type xfs --data-dev ' + part + ' ' + journal, output_loglevel='debug', env={'HOME':'/root'} )
	else:
		prep = __salt__['cmd.run']('ceph-disk prepare --cluster ceph --cluster-uuid '+ fsid + ' --fs-type xfs --data-dev ' + part, output_loglevel='debug', env={'HOME':'/root'} )
	prep += '\n'
	activate = __salt__['cmd.run']('ceph-disk activate ' + part + '1 ', output_loglevel='debug', env={'HOME':'/root'} )
	return output+prep+activate

def _prep_activate_osd_old( node, part, journal ):
	prep = __salt__['cmd.run']('ceph-deploy osd prepare '+ node + ':' + part + ':' + journal, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	activate = __salt__['cmd.run']('ceph-deploy osd activate '+ node + ':' + part, output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return prep+activate

def _remove_journal( osd_num ):
	'''
	clean up journal file after osd removed
	'''
	if os.path.exists( '/var/lib/ceph/osd/journal/osd-' + str(osd_num)):
		remove_journal = __salt__['cmd.run']('rm -rf /var/lib/ceph/osd/journal/osd-' + str(osd_num), output_loglevel='debug')
		return  str( osd_num ) + ' removed\n'
	return 'No Journal being removed ' + str( osd_num ) + ' does not exist\n'

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

def create_mon_node():
	'''
        Node creating mon with and monmap key file from master

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.create_mon_node fsid  
	'''
	node = socket.gethostname()
	mon_dir = '/var/lib/ceph/mon/ceph-' + node
	mon_key = 'ceph.mon.keyring'
	mon_map = 'monmap' 
	mon_key_file = '/tmp/'+ mon_key
	mon_map_file = '/tmp/'+ mon_map
	ceph_config_path = '/home/ceph/.ceph_sles_cluster_config'

	#output = __salt__['cmd.run']('mkdir -p ' + mon_dir, output_loglevel='debug' )
	output = __salt__['cmd.run']('mkdir -p ' + mon_dir, output_loglevel='debug', runas='ceph' )
	output += __salt__['cmd.run']('ceph-mon --mkfs -i ' + node + ' --monmap ' + mon_map_file + ' --keyring ' +\
	mon_key_file, output_loglevel='debug', runas='ceph' )
	output += __salt__['cmd.run']('touch ' + mon_dir + '/done', output_loglevel='debug', runas='ceph' )
	output += '\nEnabling ceph target service '+ node + ':' + str( __salt__['service.enable']('ceph.target') )
	output += '\nEnabling ceph-mon at '+ node + ':' + str( __salt__['service.enable']('ceph-mon@'+node) )
	output += '\nStarting ceph-mon at '+ node + ':' + str( __salt__['service.start']('ceph-mon@'+node) )
	# output += __salt__['cmd.run']('rm ' + mon_key_file,  output_loglevel='debug')
	# output += __salt__['cmd.run']('rm ' + mon_map_file,  output_loglevel='debug')
	return output

def create_keys_all():
	'''
        Node creating mon with fsid and key file from master

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.create_key_node
	'''
	node = socket.gethostname()
	output = ''
	output += __salt__['cmd.run']('ceph-create-keys --cluster ceph --id ' + node, output_loglevel='debug', env={ 'HOME':'/root'})
	return output

def new_ceph_cfg( *node_names ):
	'''
        Create new ceph cluster configuration step by step 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.new_mon node1 node2 node3 ....
	'''
	ceph_config_path = '/home/ceph/.ceph_sles_cluster_config'
	mon_keyring_name = 'ceph.mon.keyring'
	admin_keyring_name = 'ceph.client.admin.keyring'
	monmap_name = 'monmap'
	output = ''
	if not os.path.exists( ceph_config_path ):
		mkdir_log  = __salt__['cmd.run']( 'mkdir -p '+ceph_config_path, output_loglevel='debug', runas='ceph' )

	global_config = "[global]"
	uuid = __salt__['cmd.run']('uuidgen', output_loglevel='debug', runas='ceph' )
	uuid_config = "fsid = " + uuid
	mon_initial_member_config = "mon_initial_members = "
	mon_host_config = "mon_host = " 

	auth_config = "auth_cluster_required = cephx\nauth_service_required = cephx\nauth_client_required = cephx"
	filestore_config = "filestore_xattr_use_omap = true"

	node_ip = []  
	members_ip = ''
	monmap_list = ''
	if len(node_names) > 1:
		members = ', '.join( node_names )
		for node in node_names:
			ip = socket.gethostbyname(node) 
			node_ip.append( ip ) 
			monmap_list += '--add ' + node +  ' ' + str(ip) + ' '
		members_ip = ', '.join( node_ip )
	else:
		members = str(node_names[0])
		members_ip = socket.gethostbyname(str(node_names[0]))
		monmap_list += '--add ' + members + ' ' +  members_ip + ' '
	

	config_out = global_config + '\n'
	config_out += uuid_config + '\n'
	config_out += mon_initial_member_config + members + '\n'
	config_out += mon_host_config + members_ip + '\n'
	config_out += auth_config + '\n'
	config_out += filestore_config + '\n'

	ceph_config_file = ceph_config_path + '/' + 'ceph.conf' 
	logfile = open( ceph_config_file ,  "w" )
	logfile.write( config_out )
	logfile.close()
	os.chown( ceph_config_file, 1000, 100 )

	push_conf( *node_names )
	push_conf( socket.gethostname() )
	#return output

def new_mon( *node_names ):
	'''
        Create new ceph cluster configuration step by step 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.new_mon node1 node2 node3 ....
	'''
	ceph_config_path = '/home/ceph/.ceph_sles_cluster_config'
	mon_keyring_name = 'ceph.mon.keyring'
	admin_keyring_name = 'ceph.client.admin.keyring'
	monmap_name = 'monmap'
	output = ''
	if not os.path.exists( ceph_config_path ):
		mkdir_log  = __salt__['cmd.run']( 'mkdir -p '+ceph_config_path, output_loglevel='debug', runas='ceph' )

	global_config = "[global]"
	uuid = __salt__['cmd.run']('uuidgen', output_loglevel='debug', runas='ceph' )
	uuid_config = "fsid = " + uuid
	mon_initial_member_config = "mon_initial_members = "
	mon_host_config = "mon_host = " 

	auth_config = "auth_cluster_required = cephx\nauth_service_required = cephx\nauth_client_required = cephx"
	filestore_config = "filestore_xattr_use_omap = true"

	node_ip = []  
	members_ip = ''
	monmap_list = ''
	if len(node_names) > 1:
		members = ', '.join( node_names )
		for node in node_names:
			ip = socket.gethostbyname(node) 
			node_ip.append( ip ) 
			monmap_list += '--add ' + node +  ' ' + str(ip) + ' '
		members_ip = ', '.join( node_ip )
	else:
		members = str(node_names[0])
		members_ip = socket.gethostbyname(str(node_names[0]))
		monmap_list += '--add ' + members + ' ' +  members_ip + ' '
	

	config_out = global_config + '\n'
	config_out += uuid_config + '\n'
	config_out += mon_initial_member_config + members + '\n'
	config_out += mon_host_config + members_ip + '\n'
	config_out += auth_config + '\n'
	config_out += filestore_config + '\n'

	ceph_config_file = ceph_config_path + '/' + 'ceph.conf' 
	logfile = open( ceph_config_file ,  "w" )
	logfile.write( config_out )
	logfile.close()
	os.chown( ceph_config_file, 1000, 100 )

	mon_key_filename =  ceph_config_path + '/' + mon_keyring_name 
	admin_key_filename = ceph_config_path + '/' + admin_keyring_name
	monmap_filename = '/tmp/' + monmap_name
	
	output += "Create mon key ring:\n" + __salt__['cmd.run']('ceph-authtool --create-keyring ' + mon_key_filename + \
	' --gen-key -n mon. --cap mon "allow *"', output_loglevel='debug', runas='ceph' ) + '\n'
	output += "Create admin key ring:\n" + __salt__['cmd.run']('ceph-authtool --create-keyring ' + admin_key_filename + \
	' --gen-key -n client.admin --set-uid=0 --cap mon "allow *" --cap osd "allow *" --cap mds "allow"',\
	 output_loglevel='debug', runas='ceph' ) + '\n'


	join_keyring = __salt__['cmd.run']('ceph-authtool ' + mon_key_filename + ' --import-keyring ' +\
 	admin_key_filename, output_loglevel='debug', runas='ceph' )

	output += "Monmaptool create :\n" + __salt__['cmd.run']('monmaptool --create ' + monmap_list + ' --fsid ' + uuid + \
	' --clobber ' + monmap_filename, output_loglevel='debug', runas='ceph' ) + '\n'

	if len(node_names) > 1:
		for node in node_names:
			output += "Copy monkey, monmap to node -> " + node + ":\n"
			output += __salt__['cmd.shell']('salt-cp "' + node + '" ' + mon_key_filename +\
			' /tmp/' + mon_keyring_name  , output_loglevel='debug' ) + '\n'
			output += __salt__['cmd.shell']('salt-cp "' + node + '" ' + monmap_filename +\
			' /tmp/monmap' , output_loglevel='debug' ) + '\n'
			output += __salt__['cmd.shell']('salt "' + node + '" ceph_sles.purge_mon', output_loglevel='debug' ) + '\n'
			output += __salt__['cmd.shell']('salt "' + node + '" ceph_sles.create_mon_node ', output_loglevel='debug' ) + '\n'
			output += __salt__['cmd.shell']('salt "' + node + '" ceph_sles.create_mon_node ', output_loglevel='debug' ) + '\n'
	else:
		output += "Copy monkey, monmap to node -> " + node + ":\n"
		output += __salt__['cmd.shell']('salt-cp "' + str(node_names[0]) + '" ' + mon_key_filename +\
		' /tmp/' + mon_keyring_name  , output_loglevel='debug' ) + '\n'
		output += __salt__['cmd.shell']('salt-cp "' + str(node_names[0]) + '" ' + monmap_filename +\
		' ' + monmap_filename, output_loglevel='debug' ) + '\n'
		output += __salt__['cmd.shell']('salt "' + str(node_names[0]) + '" ceph_sles.purge_mon', output_loglevel='debug' ) + '\n'
		output += __salt__['cmd.shell']('salt "' + str(node_names[0]) + '" ceph_sles.create_mon_node ', output_loglevel='debug' ) + '\n'


	output += "Push conf to " + str(node_names) + ":\n"
	push_conf( *node_names )

	#if len(node_names) > 1:
		#for node in node_names:
			#output += "Create Keys " + node + ":\n"
			#output += __salt__['cmd.run']('salt "' + node + '" ceph_sles.create_keys_all' , output_loglevel='debug' )
	#else:
		#output += "Create Keys " + node_names[0] + ":\n"
		#output += __salt__['cmd.run']('salt "' + str(node_names[0]) + '" ceph_sles.create_keys_all' , output_loglevel='debug' )
	
	#return output

def new_mon_old( *node_names ):
	'''
        Create new ceph cluster configuration by running ceph-deploy new, mon
	create-initial, admin 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.new_mon node1 node2 node3 ....
	'''
	mkdir_log = ''
	deploy_new_log = ''
	node_list = ''
	for node in node_names :
		node_list = node_list + node + ' '
	
	if not os.path.exists( '/home/ceph/.ceph_sles_cluster_config' ): 
		mkdir_log  = __salt__['cmd.run']('mkdir -p /home/ceph/.ceph_sles_cluster_config', output_loglevel='debug', runas='ceph' )

	if not salt_utils.istextfile( '/home/ceph/.ceph_sles_cluster_config/ceph.conf' ):
		deploy_new_log  = __salt__['cmd.run']('ceph-deploy new '+ node_list  , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )

	out_log  = __salt__['cmd.run']('ceph-deploy --overwrite-conf mon create-initial' , output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )
	return mkdir_log + deploy_new_log + out_log

def purge_mon():
	'''
        Remove all configuration and data file of a mon node

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.purge_mon  
	'''
	node = socket.gethostname()
	ceph_conf_dir = '/etc/ceph/*'
	mon_dir = '/var/lib/ceph/mon/ceph-' + node
	keyring_files = '/var/lib/ceph/bootstrap-mds/ceph.keyring /var/lib/ceph/bootstrap-osd/ceph.keyring /var/lib/ceph/bootstrap-rgw/ceph.keyring'
	output = str( __salt__['service.stop']('ceph-mon@'+node) )
	output += __salt__['cmd.shell']('rm -rf ' + mon_dir + '/',  output_loglevel='debug')
	output += __salt__['cmd.shell']('rm -rf ' + keyring_files ,  output_loglevel='debug')
	output += __salt__['cmd.shell']('rm -rf ' + ceph_conf_dir ,  output_loglevel='debug')
	return output

def push_conf( *node_names ):
	'''
        Send cluster configuration file from to all needed nodes

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.ceph_push node1 node2 node3 ....
	'''
	c_conf_dir ='/home/ceph/.ceph_sles_cluster_config/' 
	client_key ='ceph.client.admin.keyring'
	rgw_key ='ceph.client.radosgw.keyring'
	node_list = ''
	out_log = ''
	for node in node_names:
		# node_list = node_list + node + ' '
		out_log += node + ':\n'
		out_log += __salt__['cmd.run']('salt-cp "' + node + '" ' + c_conf_dir + '/ceph.conf /etc/ceph/', output_loglevel='debug' ) + '\n'

		if salt_utils.istextfile( c_conf_dir + '/' + client_key ):
			out_log += __salt__['cmd.run']('salt-cp "' + node + '" ' + c_conf_dir + '/' + client_key + ' /etc/ceph/', output_loglevel='debug' ) + '\n'

		if salt_utils.istextfile( c_conf_dir + '/' + rgw_key ):
			out_log += __salt__['cmd.run']('salt-cp "' + node + '" '+ c_conf_dir + '/' + rgw_key + ' /etc/ceph/', output_loglevel='debug' ) + '\n'

	# need to change permission 
	# /etc/ceph/ceph.client.admin.keyring
	# ceph_key = '/etc/ceph/ceph.client.admin.keyring'
	# os.chown( ceph_key, 1000, 100 )
	
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
	if dev_list == '':
		return False
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
			time.sleep(15) # delays for 15 seconds
			if node == node_name:
				iperf_out = __salt__['cmd.run']('/usr/bin/iperf3 -c ' + master_node + ' -d' , output_loglevel='debug')
				break
	return iperf_out 

def bench_test_ruleset( replication_size=3 ):
	'''
	Test all the new ruleset with utilization 

	CLI Example:

	.. code-block:: bash
	salt 'node*' ceph_sles.bench_test_ruleset 2 
	'''
	crushmap_path = '/home/ceph/.ceph_sles_cluster_config/crushmap'
	new_bin_map = 'new_crushmap.bin'
	utilization = __salt__['cmd.run']('crushtool --test -i ' + new_bin_map + ' --show-utilization --num-rep=' + str(replication_size),
	output_loglevel='debug', runas='ceph', cwd=crushmap_path )

	return utilization

def bench_rados():
	'''
	Test all the following pool type 1) SSD 2) HDD 3) MIX
	Test replication size 2 and 3 
	Test read type rand and seq 
	Test all operation with thread count 1, CPU size, Max Core Thread total 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.bench_rados
	'''
	rbd_fio_name ='fio_test'
	bench_path = '/home/ceph/.ceph_sles_bench_report'
	pool_names = ['ssd','hdd']
	thread_counts = [1, 4, 16]
	bench_time = 100	
	

	create_pool( 'ssd_pool_2', 64, 2, 'ssd_replicated' )
	create_rbd = __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool ssd_pool_2')  + '\n'
	create_pool( 'ssd_pool_3', 64, 3, 'ssd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool ssd_pool_3')  + '\n'

	create_pool( 'hdd_pool_2', 64, 2, 'hdd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool hdd_pool_2')  + '\n'
	create_pool( 'hdd_pool_3', 64, 3, 'hdd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool hdd_pool_3')  + '\n'
	

	_bench_prep()

	for pool in pool_names:
		bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_2 bench ' + str(bench_time*2) + ' write --no-cleanup', output_loglevel='debug' )
		rep2_log = bench_path + '/' + pool + '_pool_2_write_default_nocleanup.log' 
		logfile = open( rep2_log ,  "w" )
		logfile.write( bench_result )
		logfile.close()
		os.chown( rep2_log, 1000, 100 )

		bench3_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_3 bench ' + str(bench_time*2) + ' write --no-cleanup', output_loglevel='debug' )
		rep3_log = bench_path + '/' + pool + '_pool_3_write_default_nocleanup.log' 
		logfile = open( rep3_log ,  "w" )
		logfile.write( bench3_result )
		logfile.close()
		os.chown( rep3_log, 1000, 100 )

		for thread in thread_counts:
			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_2 bench ' + str(bench_time) + ' rand -t ' + str(thread) + ' --no-cleanup', output_loglevel='debug' )
			rep2_log = bench_path + '/' + pool + '_pool_2_rand_thread_' + str(thread) + '.log' 
			logfile = open( rep2_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep2_log, 1000, 100 )

			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_3 bench ' + str(bench_time) + ' rand -t ' + str(thread) + ' --no-cleanup', output_loglevel='debug' )
			rep3_log = bench_path + '/' + pool + '_pool_3_rand_thread_' + str(thread) + '.log' 
			logfile = open( rep3_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep3_log, 1000, 100 )

			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_2 bench ' + str(bench_time) + ' seq -t ' + str(thread) + ' --no-cleanup', output_loglevel='debug' )
			rep2_log = bench_path + '/' + pool + '_pool_2_seq_thread_' + str(thread) + '.log' 
			logfile = open( rep2_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep2_log, 1000, 100 )

			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_3 bench ' + str(bench_time) + ' seq -t ' + str(thread) + ' --no-cleanup', output_loglevel='debug' )
			rep3_log = bench_path + '/' + pool + '_pool_3_seq_thread_' + str(thread) + '.log' 
			logfile = open( rep3_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep3_log, 1000, 100 )

		for thread in thread_counts:
			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_2 bench ' + str(bench_time) + ' write -t ' + str(thread), output_loglevel='debug' )
			rep2_log = bench_path + '/' + pool + '_pool_2_write_thread_' + str(thread) + '.log' 
			logfile = open( rep2_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep2_log, 1000, 100 )

			bench_result = __salt__['cmd.shell']('rados -p ' + pool + '_pool_3 bench ' + str(bench_time) + ' write -t ' + str(thread), output_loglevel='debug' )
			rep3_log = bench_path + '/' + pool + '_pool_3_write_thread_' + str(thread) + '.log' 
			logfile = open( rep3_log ,  "w" )
			logfile.write( bench_result )
			logfile.close()
			os.chown( rep3_log, 1000, 100 )

	remove_pool( 'ssd_pool_2' )
	remove_pool( 'ssd_pool_3' )
	remove_pool( 'hdd_pool_2' )
	remove_pool( 'hdd_pool_3' )
#	remove_pool( 'mix_pool_2' )
#	remove_pool( 'mix_pool_3' )

def bench_fio():
	'''
	Test all the following pool type with rbd 1) SSD 2) HDD 3) MIX
	Test replication size 2 and 3 
	Test read type rand and seq 
	Test all operation with thread count 1, CPU size, Max Core Thread total 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.bench_fio
	'''
	rbd_fio_name ='fio_test'
	bench_path = '/home/ceph/.ceph_sles_bench_report'
	pool_names = ['ssd','hdd','mix']
	bench_time = 100	
	
	create_pool( 'ssd_pool_2', 64, 2, 'ssd_replicated' )
	create_rbd = __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool ssd_pool_2')  + '\n'
	create_pool( 'ssd_pool_3', 64, 3, 'ssd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool ssd_pool_3')  + '\n'

	create_pool( 'hdd_pool_2', 64, 2, 'hdd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool hdd_pool_2')  + '\n'
	create_pool( 'hdd_pool_3', 64, 3, 'hdd_replicated' )
	create_rbd += __salt__['cmd.run']('rbd create ' + rbd_fio_name + ' --size 2048 --pool hdd_pool_3')  + '\n'

	_bench_prep()

	for pool in pool_names:
		fio_result = __salt__['cmd.shell']('fio --ioengine=rbd --rbdname=' + rbd_fio_name + ' --clientname=admin --iodepth=32 --direct=1 --rw=randwrite --bs=4K --runtime=300 --ramp_time=30 --name ' + pool + '_pool_2_test --group_reporting --pool='+ pool + '_pool_2', output_loglevel='debug' )

		fio2_log = bench_path + '/' + pool + '_fio_4K_randwrite.log'
		logfile = open( fio2_log,  "w" )
		logfile.write( fio_result )
		logfile.close()
		os.chown( fio2_log, 1000, 100 )

		fio_result = __salt__['cmd.shell']('fio --ioengine=rbd --rbdname=' + rbd_fio_name + ' --clientname=admin --iodepth=32 --direct=1 --rw=randwrite --bs=64K --runtime=300 --ramp_time=30 --name ' + pool + '_pool_2_test --group_reporting --pool='+ pool + '_pool_2', output_loglevel='debug' )

		fio2_log = bench_path + '/' + pool + '_fio_64K_randwrite.log'
		logfile = open( fio2_log,  "w" )
		logfile.write( fio_result )
		logfile.close()
		os.chown( fio2_log, 1000, 100 )

		fio_result = __salt__['cmd.shell']('fio --ioengine=rbd --rbdname=' + rbd_fio_name + ' --clientname=admin --iodepth=32 --direct=1 --rw=randwrite --bs=4K --runtime=300 --ramp_time=30 --name ' + pool + '_pool_3_test --group_reporting --pool=' + pool + '_pool_3', output_loglevel='debug' ) 

		fio3_log = bench_path + '/' + pool + '_fio_4K_randwrite.log' 
		logfile = open( fio3_log ,  "w" )
		logfile.write( fio_result )
		logfile.close()
		os.chown( fio3_log, 1000, 100 )

		fio_result = __salt__['cmd.shell']('fio --ioengine=rbd --rbdname=' + rbd_fio_name + ' --clientname=admin --iodepth=32 --direct=1 --rw=randwrite --bs=64K --runtime=300 --ramp_time=30 --name ' + pool + '_pool_3_test --group_reporting --pool=' + pool + '_pool_3', output_loglevel='debug' ) 

		fio3_log = bench_path + '/' + pool + '_fio_64K_randwrite.log' 
		logfile = open( fio3_log ,  "w" )
		logfile.write( fio_result )
		logfile.close()
		os.chown( fio3_log, 1000, 100 )

	remove_pool( 'ssd_pool_2' )
	remove_pool( 'ssd_pool_3' )
	remove_pool( 'hdd_pool_2' )
	remove_pool( 'hdd_pool_3' )

def clean_disk_partition( partlist=None):
	'''
	Remove disk partition table 

	CLI Example:

	.. code-block:: bash
	salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb,/dev/sdc,/dev/sde"
	'''
	part_list = partlist.split(",")
	disk_zap = ""
	output = ""

	for part in part_list:
		mount = __salt__['cmd.shell']('mount | grep ' + part + ' | cut -f 1 -d \' \'' )
		if mount:
			output = 'Umount ' + mount + '\n'
			output += __salt__['cmd.shell']('umount ' + mount  )
		disk_zap = 'Remove Partition ' + part + '\n'
		disk_zap += __salt__['cmd.shell']('ceph-disk zap ' + part , output_loglevel='debug' )
		disk_zap += __salt__['cmd.shell']('partx -a ' + part , output_loglevel='debug' )
	return output + '\n' + disk_zap

def clean_disk_partition_old( nodelist=None, partlist=None):
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

def create_pool( pool_name, pg_num, replication_size, ruleset_name='replicated_ruleset', pool_type='replicated' ):
	'''
	Create a pool in cluster

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.create_pool ssd_pool_name 100<pg_num> 2<replicate> ruleset_name pooltype<default replicated> 
	'''
	create_pool = __salt__['cmd.run']('ceph osd pool create ' + pool_name + ' ' + str(pg_num) + ' ' + pool_type + ' ' + ruleset_name , 
	output_loglevel='debug', cwd='/etc/ceph' )

	create_pool += __salt__['cmd.run']('ceph osd pool set ' + pool_name + ' size ' + str(replication_size),
	output_loglevel='debug', cwd='/etc/ceph' )

	# create_pool = __salt__['cmd.run']('ceph osd pool set ' + pool_name + ' rulsset ' + ruleset_num,
	# output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )

	return create_pool
	

def disk_info():
	'''
	Get all the disk device from nodes 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.disk_info 
        '''
	result = __salt__['cmd.shell']('lsblk | grep ^sd*', output_loglevel='debug')
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
		_fstab_add_part( new_part_label, journal_path ) 

	new_part_mount = __salt__['cmd.run']('mount '+ journal_path, output_loglevel='debug' )

	new_part_mount += "\n\n"
	new_part_mount += __salt__['cmd.run']('parted ' + partition_dev + ' unit s print free', output_loglevel='debug' )
	new_part_mount += "\n\n"
	new_part_mount += __salt__['cmd.run']('mount', output_loglevel='debug' )
	return new_part_mount

def prep_osd_ssd_journal( nodelist=None, partlist=None):

	'''
	Prepare all the osd and activate them 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.prep_osd "node1,node2,node3" "/dev/sda5,/dev/sdb,/dev/sdc,/dev/sdd,/dev/sde"
	'''
	journal_path = '/var/lib/ceph/osd/journal/osd'
	return prep_osd( nodelist=None, partlist=None, journal_path=None)


def prep_osd( nodelist=None, partlist=None, journal_path=None):
	'''
	Prepare all the osd and activate them 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.prep_osd "node1,node2,node3" "/dev/sda5,/dev/sdb,/dev/sdc,/dev/sdd,/dev/sde"

	'''
	#journal_path = '/var/lib/ceph/osd/journal/osd'
		
	result = ""
	node_list = nodelist.split(",")
	part_list = partlist.split(",")

	new_osd_id = __salt__['cmd.shell']('ceph osd ls | tail -n 1', output_loglevel='debug', env={'HOME':'/root'} )

	if not new_osd_id:
		osd_num = 0
	else:
		osd_num = int(new_osd_id)


	for part in part_list:
		for node in node_list:
			if journal_path: 
				result += __salt__['cmd.run']('salt --async "' + node + '" ceph_sles.prep_activate_osd_local ' + part + ' ' + journal_path + '-' + str(osd_num), output_loglevel='debug' ) + '\n'
			else:
				result += __salt__['cmd.run']('salt --async "' + node + '" ceph_sles.prep_activate_osd_local ' + part, output_loglevel='debug' ) + '\n'
			# result += _prep_activate_osd( node, part, journal_path+str(osd_num))
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
			mounted_osd += "\n" + __salt__['cmd.shell']('mount | grep ' + osd + '| cut -f 3 -d " "' , output_loglevel='debug')
			mounted_osd += "\t" + __salt__['cmd.shell']('mount | grep ' + osd + '| cut -f 1 -d " "' , output_loglevel='debug')
			file_list += "\n" + osd
	return "Possible OSD is not clean in /var/lib/ceph/osd/ :\n" + file_list + "\n\nCurrently mounted osd :\t Mount point:\n" + mounted_osd


def purge_osd( *osd_num ):
	'''
	Umount the osd mount point and clean up the host osd leave over files

	CLI Example:

	.. code-block:: bash
	salt 'node*' ceph_sles.purge_osd 0 1 2 3 
	'''
	prepare_active_lock = '/var/lib/ceph/tmp/ceph-disk.prepare.lock /var/lib/ceph/tmp/ceph-disk.activate.lock'
	clean_log = ''
	stop = ''
	for remove_osd in osd_num:
		stop += str( __salt__['service.stop']('ceph-osd@' + str(remove_osd)))
		for ceph_path in _list_osd_files().split("\n"):
			mounted = __salt__['cmd.shell']('mount | grep "' + ceph_path + '"| grep ceph-' + str(remove_osd) + '| cut -f 3 -d " "', output_loglevel='debug')
			if mounted:
				clean_log += 'umount ' + mounted + '\n'
				clean_log += _umount_path( mounted ) + '\n'
				mounted = False
			if os.path.exists( '/var/lib/ceph/osd/ceph-' + str(remove_osd)):
				clean_log += 'remove /var/lib/ceph/osd/ceph-' + str(remove_osd) + '\n'
				clean_log += __salt__['cmd.run']('rm -rf /var/lib/ceph/osd/ceph-' + str(remove_osd), output_loglevel='debug')
		clean_log += 'remove journal ' + _remove_journal( remove_osd )
	clean_log +=  __salt__['cmd.run']('rm -rf ' + prepare_active_lock, output_loglevel='debug')
	return clean_log

def remove_osd( *osd_num ):
	'''
	Remove osd from the cluster 

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.remove_osd 0 1 2 3 

	'''
	ceph_conf = '/home/ceph/.ceph_sles_cluster_config'
	admin_key = 'ceph.client.admin.keyring'
	remove = "" 
	for osd in osd_num:
		remove += __salt__['cmd.run']('ceph osd down osd.'+ str(osd) + ' -k ' + admin_key, output_loglevel='debug', runas='ceph', cwd=ceph_conf ) + '\n'
		remove += __salt__['cmd.run']('ceph osd crush remove osd.'+ str(osd) + ' -k ' + admin_key, output_loglevel='debug', runas='ceph', cwd=ceph_conf ) + '\n'
		remove += __salt__['cmd.run']('ceph auth del osd.'+ str(osd) + ' -k ' + admin_key, output_loglevel='debug', runas='ceph', cwd=ceph_conf ) + '\n'
		remove += __salt__['cmd.run']('ceph osd rm '+ str(osd) + ' -k ' + admin_key, output_loglevel='debug', runas='ceph', cwd=ceph_conf ) + '\n'

	return remove

def remove_pool( pool_name ):
	'''
	Remove a pool in cluster

	CLI Example:

	.. code-block:: bash
	salt 'node1' ceph_sles.remove_pool pool_name
	'''
	return  __salt__['cmd.run']('ceph osd pool delete ' + pool_name + ' ' + pool_name + '  --yes-i-really-really-mean-it ', 
	output_loglevel='debug', runas='ceph', cwd='/home/ceph/.ceph_sles_cluster_config' )

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
	tree_view_json =  __salt__['cmd.shell']('ceph osd tree --format json | grep {', output_loglevel='debug', cwd='/etc/ceph', runas='ceph' )
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

def _crushmap_add_hdd_ssd_tree( *node_names ):
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

	prep = "get crushmap:\n" + __salt__['cmd.run']('ceph osd getcrushmap -o ' + orig_bin_map, output_loglevel='debug', runas='ceph', cwd=crushmap_path )
	prep += "create text crushmap:\n" + __salt__['cmd.run']('crushtool -d ' + orig_bin_map + ' -o ' + orig_txt_map , output_loglevel='debug', runas='ceph', cwd=crushmap_path )
	prep += "create new_crushmap.txt:\n" +  __salt__['cmd.run']('cp ' + orig_txt_map + ' ' + new_txt_map  , output_loglevel='debug', runas='ceph', cwd=crushmap_path )

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

def _remove_crushmap_bucket_update( bucket_section ):
	'''
	Read the old crushmap and get the bucket section and remove 
	saltstack update disktype osd_ssd {}, disktype osd_hdd {} 
	and root root_ssd {}, root root_hdd {} 
	'''
	# keep that in 2 states 'keep', 'remove', 'remove-end'
	state = 'keep' 
	output = ""
	section = StringIO.StringIO( bucket_section )
	for line in section:
		if line.startswith( 'disktype osd_ssd' ) or line.startswith( 'disktype osd_hdd' ) or \
		line.startswith( 'root root_ssd' ) or line.startswith( 'root root_ssd' ):
			state = 'remove' 
		if line.startswith( '}' ):
			if( state == 'remove' ):
				state = 'remove-end'
		if state == 'keep':
			output += line
		if state == 'remove-end':
			state == 'keep'
	return output

def _read_crushmap_has_ruleset_update( ruleset_section ):
	'''
	Read the old crushmap and see the ssd and hdd ruleset already
	exist, if it does return True or else False
	'''
	section = StringIO.StringIO( ruleset_section )
	for line in section:
		if line.startswith( 'rule ssd_replicated' ) or line.startswith( 'rule hdd_replicated' ):
			return True
	return False

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


	ruleset_list += '\n' + end_line + '\n'

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
	output = _prepare_crushmap()
	# get the first section of the crushmap text file 
	before_type = _read_crushmap_begin_section( begin_line, type_line )
	# add the disktype into the crushmap type list
	new_type = _crushmap_add_disktype()
	# get the bucket section until the ruleset
	bucket_list = _read_crushmap_begin_section( bucket_line, rule_line )
	# remove if the bucket list has been updated before 
	bucket_list = _remove_crushmap_bucket_update( bucket_list )
	# add the pure ssd and pure hdd bucket 
	bucket_ssd_hdd = _crushmap_add_hdd_ssd_tree( *node_names )
	# get the ruleset of the curshmap
	ruleset_list = _read_crushmap_begin_section( rule_line, end_line )
	
	# if the rule list has been updated before leave it alone 
	if not _read_crushmap_has_ruleset_update( ruleset_list ):
		# get the highest number of ruleset id + 1 
		next_ruleset_id = _read_ruleset_next_id( ruleset_list )
		# let's fix this later, I'm sure there is better way to setup min and max 
		min_size = 1
		max_size = 3 
		# add the ssd and hdd replicated ruleset 
		ruleset_list += _crushmap_add_ssd_hdd_ruleset( 'replicated', next_ruleset_id, min_size, max_size )
		ruleset_list += _crushmap_add_ssd_hdd_ruleset( 'erasure', next_ruleset_id+2, min_size, max_size )

	ruleset_list += '\n' + end_line + '\n'

	new_crushmap = before_type + new_type + bucket_list + bucket_ssd_hdd + ruleset_list
	new_crushmap_file = open( crushmap_path + '/' + new_txt_map, "w" ) 
	new_crushmap_file.write( new_crushmap )
	new_crushmap_file.close()

	return output + _update_crushmap()


def ntp_update( master_node ):
	'''
	Get all the node sync times with salt-master

	CLI Example:

	.. code-block:: bash
	salt '*' ceph_sles.bench_network admin_node
	'''

	ntp_out = False
	node_name = socket.gethostname()

	if node_name == master_node:
		ntp_out = 'Starting ntpd ' + str( __salt__['service.start']('ntpd'))
	else:
		ntp_out = __salt__['cmd.run']('ntpdate -u salt-master' , output_loglevel='debug') +'\n'
		ntp_out += __salt__['cmd.run']('ntpdate -u salt-master' , output_loglevel='debug') +'\n'
		ntp_out += __salt__['cmd.run']('ntpdate -u salt-master' , output_loglevel='debug') +'\n'
	return ntp_out

def _radosgw_create_pool():
	'''
	Create all the needed pool for radosgw. (Should this be external?)

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.radosgw_create_pool 
	'''
	output = create_pool( '.intent-log', 32, 2, 'hdd_replicated' )
	output += create_pool( '.log', 128, 2, 'hdd_replicated' )
	output += create_pool( '.rgw', 32, 2, 'ssd_replicated' )
	output += create_pool( '.rgw.control', 32, 2, 'ssd_replicated' )
	output += create_pool( '.rgw.gc', 32, 2, 'ssd_replicated' )
	output += create_pool( '.rgw.buckets', 32, 2, 'ssd_replicated' )
	output += create_pool( '.rgw.buckets.index', 32, 2, 'ssd_replicated' )
	output += create_pool( '.rgw.buckets.extra', 32, 2, 'ssd_replicated' )
	output += create_pool( '.usage', 32, 2, 'ssd_replicated' )
	output += create_pool( '.users.email', 32, 2, 'ssd_replicated' )
	output += create_pool( '.users', 32, 2, 'ssd_replicated' )
	output += create_pool( '.users.swift', 32, 2, 'ssd_replicated' )
	output += create_pool( '.users.uid', 32, 2, 'ssd_replicated' )
	return output

def _radosgw_keygen( gateway_node ):
	'''
	Create keyring for radosgw with full access. (Should this be external?)

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.radosgw_key
	'''
	ceph_config_path = '/home/ceph/.ceph_sles_cluster_config'
	radosgw_keyring  = 'ceph.client.radosgw.keyring'

	keygen = __salt__['cmd.run']('ceph-authtool -C -n client.radosgw.'+ gateway_node + ' --gen-key ' + ceph_config_path + '/' + radosgw_keyring , output_loglevel='debug', runas='ceph') +'\n'
	keygen += __salt__['cmd.run']('ceph-authtool -n client.radosgw.' + gateway_node + ' --cap osd "allow rwx" --cap mon "allow rwx"  ' + ceph_config_path + '/' + radosgw_keyring , output_loglevel='debug', runas='ceph') +'\n'
	keygen += __salt__['cmd.run']('ceph auth add client.radosgw.' + gateway_node + ' --in-file ' + ceph_config_path + '/' + radosgw_keyring , output_loglevel='debug', runas='ceph') +'\n'
	return keygen

def _radosgw_config_update( gateway_node ):
	'''
	Create keyring for radosgw with full access. (Should this be external?)

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.radosgw_config_update
	'''
	radosgw_var_run_dir = '/var/run/ceph-radosgw'
	radosgw_var_log_dir = '/var/log/ceph-radosgw'
	radosgw_sock = 'ceph.client.radosgw.fastcgi.sock'
	radosgw_admin_sock = 'ceph.client.radosgw.asok'
	radosgw_log = 'ceph.client.radosgw.log'
	ceph_conf_dir = '/etc/ceph'
	radosgw_keyring  = 'ceph.client.radosgw.keyring'

	conf_out = '[client.radosgw.' + gateway_node + ']\n'
	conf_out += 'host = ' + gateway_node + '\n'
	conf_out += 'keyring = ' + ceph_conf_dir + '/' + radosgw_keyring + '\n'
	conf_out += 'rgw_socket_path = ' + radosgw_var_run_dir + '/' + radosgw_sock + '\n'
	conf_out += 'admin_socket = ' + radosgw_var_run_dir + '/' + radosgw_admin_sock + '\n' 
	conf_out += 'log_file = ' + radosgw_var_log_dir + '/' + radosgw_log + '\n'
	conf_out += 'rgw_frontends = civetweb port=80\n' 


	return conf_out

def _rewrite_conf_gateway( gateway_node ):
	'''
	Read the ceph.conf and take out the radosgw configuration if exist
	'''
	ceph_config_path = '/home/ceph/.ceph_sles_cluster_config'
	ceph_conf = 'ceph.conf'
	old_conf = ""
	take_out = False

	# take out the old client radosgw conf if any
	for line in fileinput.input( ceph_config_path + '/' + ceph_conf ):
		if take_out:
			if line.startswith( '[' ):
				take_out = False
		if line.startswith( '[client.radosgw' ):
			take_out = True
		if not take_out:
			old_conf += line


	old_conf += '\n'
	new_conf = _radosgw_config_update( gateway_node )

	new_conf_file = open( ceph_config_path + '/' + ceph_conf , "w" ) 
	new_conf_file.write( old_conf )
	new_conf_file.write( new_conf )
	new_conf_file.close()
	return ceph_config_path + '/' + ceph_conf  + ' updated\n'


def create_rados_gateway( gateway_node ):
	'''
	Create rados gateway and enable gateway into the cluster

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.create_rados_gateway gateway_node
	'''

	out = _radosgw_create_pool()
	out += _radosgw_keygen( gateway_node )
	out += _rewrite_conf_gateway( gateway_node )
	out += push_conf( gateway_node )
	out += '\nEnabling radosgw service '+ gateway_node + ':\n' 
	out += __salt__['cmd.run']('salt "' + gateway_node + '" service.enable ceph.radosgw@'+gateway_node, output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('salt "' + gateway_node + '" service.start ceph.radosgw@'+gateway_node, output_loglevel='debug' ) + '\n'
	return out

def create_cache_tier( pool_name ):
	'''
	Create two pool ssd in front of the hdd to create cache tier 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.create_cache_tier Pool_Name 
	'''
	out = create_pool( pool_name + "_write_cache",  64,  2,  "ssd_replicated" )  + '\n'
	out = create_pool( pool_name + "_read_cache",  64,  2,  "ssd_replicated" )  + '\n'
	out += create_pool( pool_name ,  64,  2,  "hdd_replicated" )  + '\n'
	out += __salt__['cmd.run']('ceph osd tier add ' + pool_name + ' ' + pool_name + '_write_cache ' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier cache-mode ' + pool_name + '_write_cache writeback' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier cache-mode ' + pool_name + '_read_cache readforward' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier set-overlay ' + pool_name + ' ' + pool_name + '_write_cache ' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier set-overlay ' + pool_name + ' ' + pool_name + '_read_cache ' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache hit_set_type bloom' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache hit_set_count 2' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache hit_set_period 300' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache target_max_bytes 10485760000' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache target_max_objects 10000' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache cache_target_dirty_ratio 0.01' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd pool set ' + pool_name + '_write_cache cache_target_full_ratio 0.1' , output_loglevel='debug' ) + '\n'

	return out

def remove_cache_tier( pool_name ):
	'''
	remove two read write pool in front of the hdd 

	CLI Example:

	.. code-block:: bash
	salt 'salt-master' ceph_sles.remove_cache_tier Pool_Name 
	'''
	out = __salt__['cmd.run']('ceph osd tier cache-mode ' + pool_name + '_read_cache none' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier remove ' + pool_name + ' ' + pool_name + '_read_cache ' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier cache-mode ' + pool_name + '_write_cache forward' , output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier remove-overlay ' + pool_name, output_loglevel='debug' ) + '\n'
	out += __salt__['cmd.run']('ceph osd tier remove ' + pool_name + ' ' + pool_name + '_write_cache ' , output_loglevel='debug' ) + '\n'
	out += remove_pool( pool_name + "_write_cache")  + '\n'
	out += remove_pool( pool_name + "_read_cache")  + '\n'
	out += remove_pool( pool_name )  + '\n'

	return out
