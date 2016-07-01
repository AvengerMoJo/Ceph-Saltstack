#!/usr/bin/python
# -*- coding: utf-8 -*-


import hmac
from hashlib import sha1
from time import time

method = 'GET'
host = 'http://salt-master:80'
duration_in_seconds = 300  # Duration for which the url is valid
expires = int(time() + duration_in_seconds)
path = '/swift/v1/video/suse.mp4'
key = 'KBJG16sjS86sIMzHg834P8RsodRVNKW0Xe4Hxkq2'
hmac_body = '%s\n%s\n%s' % (method, expires, path)
hmac_body = hmac.new(key, hmac_body, sha1).hexdigest()
sig = hmac.new(key, hmac_body, sha1).hexdigest()
rest_uri = "{host}{path}?temp_url_sig={sig}&temp_url_expires={expires}".format(
             host=host, path=path, sig=sig, expires=expires)
print rest_uri
