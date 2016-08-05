#!pydsl

import os
import socket

hostname = socket.gethostname()

def fail_state():
    return False

__pydsl__.set(ordered=True)

s_ceph = state('ceph').pkg.installed(names=['salt-ceph', 'python-ceph-cfg', 'ceph'])

new_ceph_conf_file = '/home/ceph/.ceph_sles_cluster_config/ceph.conf'

# check conf file and mon pillar info:
ceph_conf = state('/etc/ceph/ceph.conf')
if 'master' in hostname:
    if os.path.exists ( new_ceph_conf_file ):
        ceph_conf = state('/etc/ceph/ceph.conf')\
        .file.managed('/etc/ceph/ceph.conf', source=new_ceph_conf_file, user='root', group='root', mode='644', makedir=True)
    else:
        state('/etc/ceph/ceph.conf').cmd.call( fail_state )
#else:
    #ceph_conf = state('/etc/ceph/ceph.conf')\
    #.file.managed('/etc/ceph/ceph.conf', source='salt://ceph/ceph.conf', user='root', group='root', mode='644', makedir=True, contents_pillar='ceph:ceph.conf')

# create key for pillar:
s_create_key = state('new_key_pillar') 
s_create_key.module.run( name ='ceph_sles.new_key_pillar' )

# keyring_admin_save:
s_admin = state( 'keyring_admin_save' )
s_admin.module.run( name='ceph.keyring_save', kwargs=dict( keyring_type='admin', secret=__pillar__.get('admin_key') ))\
.require( s_create_key.module )

# for mon
if 'mon' in hostname:
    # keyring_mon_save:
    s_mon = state( 'keyring_mon_save' )
    s_mon.module.run( name='ceph.keyring_save', kwargs=dict( keyring_type='mon', secret=__pillar__.get('mon_key') ))\
    .require( s_create_key.module )

    # mon_create:
    s_mon_create = state( 'mon_create' )
    s_mon_create.nodes = __pillar__.get('mon')
    if hostname in s_mon_create.nodes:
        s_mon_create.module.run( name='ceph.mon_create' )\
        .require( s_admin.module )\
        .require( s_mon.module )

s_cluster_status = state( 'cluster_status' )
s_cluster_status.module.run( name='ceph.cluster_quorum' )\
.require( s_admin.module )

# for osd
if 'osd' in hostname:
    # keyring_osd_save:
    s_osd = state( 'keyring_osd_save' )
    s_osd.module.run( name='ceph.keyring_save', kwargs=dict( keyring_type='osd', secret=__pillar__.get('osd_key') ))\
    .require( s_create_key.module )

    # keyring_osd_auth_add:
    s_osd_auth = state( 'keyring_osd_auth_add' )
    s_osd_auth.module.run( name='ceph.keyring_osd_auth_add' )\
    .require( s_cluster_status.module )\
    .require( s_osd.module )

    #devs = __pillar__.get( 'osd_dev' )
    devs = __pillar__.get( hostname )['osd_dev']
    dev = devs.split(' ')
    for d in dev:
        s_prepare = state( 'osd_prepare' )
        s_prepare.module.run( name='ceph.osd_prepare', kwargs=dict( osd_dev=d ) )\
        .require( s_osd_auth.module )

        s_activate = state( 'osd_activate' )
        s_activate.module.run( name='ceph.osd_activate', kwargs=dict( osd_dev=d ) )\
        .require( s_prepare.module )

