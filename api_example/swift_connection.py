# -*- coding: utf-8 -*-
#!/usr/bin/python


import swiftclient

import subprocess as sp
import json

output = sp.check_output("radosgw-admin user info --uid=alex", shell=True)
keyinfo = json.loads( output )
secret_key = ""

for user in  keyinfo["swift_keys"]:
        if user["user"] == "alex:swift":
                secret_key = user["secret_key"]


user = 'alex:swift'
# access_key = 'UPfCwzqdaNz7bXSUE1LPOqMK1NNe4MNhFKn6GREW'
url = 'http://salt-master/auth'

print ( 'Connect to the obj-store with swiftclient' )
connect = swiftclient.Connection(
        user=user,
        key=secret_key,
        authurl=url,
)

new_container_name = 'new-container'
print ( 'Create a container :' + new_container_name )
connect.put_container( new_container_name )

hello_obj = 'hello.txt'

print ( 'Put a file {' + hello_obj + '} into ' + new_container_name )
with open( hello_obj, 'r') as hello_file:
	connect.put_object( new_container_name, hello_obj,
		contents= hello_file.read(),
		content_type='text/plain' )

print ( 'List all the container that I own ' )
for container in connect.get_account()[1]:
        print ( 'Container name :' + container['name'] )

for data in connect.get_container( new_container_name )[1]:
        print ( '{0}\t{1}\t{2}'.format( data['name'], data['bytes'], data['last_modified']) )

new_hello = 'new_hello.txt'
print ( 'Write out the data from {' + hello_obj + '} of container ' + new_container_name  + ' into a new file ' + new_hello )
obj_data = connect.get_object( new_container_name, hello_obj )
with open( new_hello, 'w' ) as my_hello:
        my_hello.write( obj_data[1] )


with open( hello_obj, 'r') as hello_file:
	connect.put_object( new_container_name, hello_obj,
		contents= hello_file.read(),
		content_type='text/plain' )

print ( 'Create a container : video' )
try:
	connect.put_container( 'video' )
except:
	print ( 'Container {video} cannot be created' )

video_name = 'SUSE Enterprise Storage Fundamentals (Ceph) 中文字幕.mp4'
video_path = '/home/ceph/Videos'
print ( 'Put a video file {' + video_name + '} into container {video}' )
with open( video_path + '/' + video_name, 'r') as video_file:
	connect.put_object( 'video' , 'suse.mp4',
		contents= video_file.read(),
		content_type='video/mp4' )



print ( 'Remote object {' + hello_obj + '} of container' )
connect.delete_object( new_container_name, hello_obj )
print ( 'Remote container {' + new_container_name + '}' )
connect.delete_container( new_container_name )


