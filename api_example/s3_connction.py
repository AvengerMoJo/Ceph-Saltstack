#!/usr/bin/python


import boto
import boto.s3.connection

import subprocess as sp
import json

output = sp.check_output("radosgw-admin user info --uid=alex", shell=True)
keyinfo = json.loads( output )
access_key = ""
secret_key = ""

for user in  keyinfo["keys"]:
        if user["user"] == "alex":
                access_key = user["access_key"]
                secret_key = user["secret_key"]

# access_key = "W8122382EMUKTS3Q6F87"
# secret_key = "NRLgXNCO59bSiocTMBdVQiY8zfwGAbvAJ228juMR"

print access_key
print secret_key

gateway_host = "salt-master"
gateway_port = 80

def print_all_bucket( connect ):
	print ( "List all the buckets in the object store { " )
	for bucket in connect.get_all_buckets():
		print "\t{name} \t {created}".format(
			name = bucket.name,
			created = bucket.creation_date
		)
	print ( "}\n" )

print ( "Python2.x Demo S3 API\n" )
print ( "Connecting to ... http://" + gateway_host + ":" + str( gateway_port ) + "\n" )
connect = None
connect = boto.connect_s3( 
	aws_access_key_id = access_key,
	aws_secret_access_key = secret_key,
	host = gateway_host,
	port = gateway_port, 
	is_secure = False,
	calling_format = boto.s3.connection.OrdinaryCallingFormat()
	)

print_all_bucket( connect )

new_bucket_name = 'new-test-bucket'
print ( "Try to create a bucket :" + new_bucket_name + "\n" ) 
bucket = connect.create_bucket( new_bucket_name )

print_all_bucket( connect )

public_obj_name = 'Hello_Object.txt'
public_obj_content = 'Hello World!'

private_obj_name = 'Private.txt'
private_obj_content = 'Fxxx xlkjlakjdfjs!'

print ( "Create a obejct {" + public_obj_name + "} in bucket  :" + new_bucket_name + "\n" ) 

public_key = bucket.new_key( public_obj_name )
public_key.set_contents_from_string( public_obj_content ) 
public_key.set_canned_acl('public-read')

public_url = public_key.generate_url( 0, query_auth=False, force_http=True )
print ( "Public object {" + public_obj_name + "} url { \n" + public_url + "\n}\n") 

print ( "Create a private obejct {" + private_obj_name + "} in bucket  :" + new_bucket_name + "\n" ) 
private_key = bucket.new_key( private_obj_name )
private_key.set_contents_from_string( private_obj_content ) 
private_key.set_canned_acl('private')

private_url = private_key.generate_url( 3600, query_auth=True, force_http=True )
print ( "Private object {" + private_obj_name + "} url { \n" + private_url + "\n}\n") 

video_name = "SUSE Enterprise Storage powered by Ceph.mp4"
video_path = "/home/ceph/Videos"
print ( "Try to Upload a vidoe :" + video_name + "\n" ) 
video_key = bucket.new_key ( video_name )
video_key.set_contents_from_filename( video_path + "/" + video_name ) 
video_key.set_canned_acl('public-read')
video_url = video_key.generate_url( 0, query_auth=False, force_http=True )
print ( "Video object {" + video_name + "} url { \n" + video_url + "\n}\n") 


# bucket.delete_key( public_key ) 
# bucket.delete_key( private_key ) 
# bucket.delete_key( video_name ) 

print ( "Try to delete a bucket :" + new_bucket_name + "\n" ) 
bucket = connect.delete_bucket( new_bucket_name )

print_all_bucket( connect )





