# -*- coding: utf-8 -*-
'''
 AvengerMoJo (alau@suse.com) 
 A SaltStack interface for Ceph Deploy and Configuration

'''

# Import Python libs for logging
import logging

# Import salt library for running remote commnad
import salt.modules.cmdmod as salt_cmd
import salt.modules.pkg as salt_pkg


log = logging.getLogger(__name__)
log.info('Create ssh key from admin node')


__virtual_name__ = 'ceph_sles'

def __virtual__():
	if __grains__.get('os',False) != 'SLES':
		return False
	if pkg.version('ceph',False) < '0.94':
		echo 'Testing'
		return False
	return __virtual_name__
	# return 'ceph_sles'

def keygen(): 
	'''
	Create ssh key from the admin node
	Admin node should be the one running
	ceph-deploy in the future

	CLI Example:

	..  code-block:: bash
		salt 'node1' ceph_sles.keygen
	'''

#    out = __salt__['cmd.run_stdout']('ssh-keygen', output_loglevel='debug')
	sshkey = salt_cmd.run('ssh-keygen', output_loglevel='debug', runas='ceph')
	return True


