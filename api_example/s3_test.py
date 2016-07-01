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

from boto.s3.key import Key

k = Key( bucket )
k.key = 'text'
k.set_contents_from_string('This is a test of S3')

old_bucket = connect.get_bucket('new-test-bucket')
old_k = Key( old_bucket )
old_k.key = 'text'
print( 'Test result = ' + old_k.get_contents_as_string() )

print ( "Try to delete a bucket :" + new_bucket_name + "\n" ) 
bucket = connect.delete_bucket( new_bucket_name )
print_all_bucket( connect )





