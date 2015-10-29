# -*- coding: utf-8 -*-
'''
 AvengerMoJo (alau@suse.com) 
 A SaltStack interface for Ceph Deploy and Configuration

'''

# Import Python libs for logging
import logging

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
		log.info('Error sshpass package not find, need to be installed' )
		return False
	if not salt_utils.which('sshpass') :
		log.info('Error sshpass package not find, need to be installed' )
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

	out_log  = __salt__['cmd.run_stdout']('ssh-keygen -b 2048 -t rsa -f /home/ceph/.ssh/id_rsa -q -N ""', output_loglevel='debug', runas='ceph' )
	# sshkey = salt_cmd.run('ssh-keygen', output_loglevel='debug', runas='ceph')
	return True


def send_key( *node_names ):
	'''
        Send ssh key from the admin node to the rest of the node allow 
        ceph-deploy in the future

        CLI Example:

        ..  code-block:: bash
                salt 'node1' ceph_sles.send_key node1 node2 node3 ....
        '''
	for node in node_names :
		out_log  = __salt__['cmd.run_stdout']('ssh-keyscan '+ node +' >> ~/.ssh/known_hosts'  , output_loglevel='debug', runas='ceph' )
		# assume the kiwi image predefine user ceph with password suse1234
		out_log  = __salt__['cmd.run_stdout']('sshpass -p "suse1234" ssh-copy-id ceph@'+node , output_loglevel='debug', runas='ceph' )
	return True



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
	
	out_log  = __salt__['cmd.run_stdout']('ceph-deploy new '+ node_list  , output_loglevel='debug', runas='ceph' )
	out_log  = __salt__['cmd.run_stdout']('ceph-deploy mon create-initial' , output_loglevel='debug', runas='ceph' )
	out_log  = __salt__['cmd.run_stdout']('ceph-deploy admin '+ node_list  , output_loglevel='debug', runas='ceph' )
	return True


