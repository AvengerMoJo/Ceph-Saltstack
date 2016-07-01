import subprocess as sp
from subprocess import call
import json

output = sp.check_output("radosgw-admin user info --uid=alex", shell=True)
keyinfo = json.loads( output )
access_key = ""
secure_key = ""


print output 
for user in  keyinfo["keys"]:
	if user["user"] == "alex":
		access_key = user["access_key"]
		secure_key = user["secret_key"]

print keyinfo["keys"][0]["access_key"]
print access_key
print secure_key


