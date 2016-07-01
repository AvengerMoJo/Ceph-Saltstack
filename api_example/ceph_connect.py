# -*- coding: utf-8 -*-
#!/usr/bin/python

import rados, sys

conf_file = "/etc/ceph/ceph.conf"
keyring_file = "/etc/ceph/ceph.client.admin.keyring"
cluster = rados.Rados(conffile = conf_file, conf = dict (keyring = keyring_file ))

print ( "librados version: " + str(cluster.version()) )
print ( "Will attempt to connect to: " + str(cluster.conf_get('mon initial members')) )

cluster.connect()
print ( "Cluster ID: " + cluster.get_fsid() )

print ( "Cluster Statistics\n==================" )
cluster_stats = cluster.get_cluster_stats()

for key, value in cluster_stats.iteritems():
	print key, value

print ( "Let's play with Pool\n===============" )
print ( "Available Pools\n----------------" )
pools = cluster.list_pools()
for pool in pools:
	print pool

new_pool_name = "hello_pool" 
try :
	print ( "\nCreate '" + new_pool_name + "' Pool\n------------------" )
	cluster.create_pool( new_pool_name )
except :
	print ( "\nPool unclean delete '" + new_pool_name + "' Pool\n------------------" )
	cluster.delete_pool( new_pool_name )
	sys.exit()

print ( "Pool named '" + new_pool_name + "' exists: " + str(cluster.pool_exists( new_pool_name )) )
print ( "Verify '" + new_pool_name + "' Pool Exists\n-------------------------" )
pools = cluster.list_pools()
for pool in pools:
	print pool

print ( "Delete '" + new_pool_name + "' Pool\n------------------" )
cluster.delete_pool( new_pool_name )
print ( "Pool named '" + new_pool_name + "' exists: " + str(cluster.pool_exists( new_pool_name )) )

cluster.create_pool( new_pool_name )
io_context = cluster.open_ioctx( new_pool_name )

hello_obj = "hello_obj"
hello_obj_content = "Hello World!"
hello_obj_zh_content = "你好世界!" 
# hello_obj_zh_content = unicode( "你好世界!" , "utf-8" )
lang = "zh_TW.utf-8"
print ( "Writing object '" + hello_obj + "' with contents '" + hello_obj_content + "' to pool '" + new_pool_name + "'." )
io_context.write_full( hello_obj, hello_obj_content )

print ( "Contents of object '" + hello_obj + "'\n------------------------" )
print io_context.read( hello_obj )

print ( "Removing object '" + hello_obj + "'" )
io_context.remove_object( hello_obj )

io_context.write( hello_obj, hello_obj_zh_content )
print ( "Writing XATTR 'lang' with value '" + lang + "' to object '" + hello_obj + "'" )
io_context.set_xattr( hello_obj, "lang", lang )

print ( "Getting XATTR 'lang' from object '" + hello_obj + "'\n" )
print ( io_context.get_xattr( hello_obj, "lang") ) 

obj_iterator = io_context.list_objects()

while True:
	try:
		rados_obj = obj_iterator.next()
		print ( "Object information = " + rados_obj.read() ) 
	except StopIteration:
		break	

io_context.remove_object( hello_obj )
cluster.delete_pool( new_pool_name )

print ( "Closing context ( pool )." )
io_context.close()

print ( "Shutdown the connection. ( cluster ) " )
cluster.shutdown()
