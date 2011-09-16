import datetime
import email.utils
import inspect
import json
import mimetypes
import os.path
import time
import uuid

from vortex import Application, HTTPResponse, Resource, authenticate, format, json2xml, signed_cookie, xsrf
from vortex.responses import *

class DictResource(Resource):
    def __init__(self, sub_resources=None):
        Resource.__init__(self)
        self.sub_resources = sub_resources or {}

    def __getitem__(self, name):
        return self.sub_resources[name]


class MutableDictResource(DictResource):
    def __setitem__(self, name, value):
        self.sub_resources[name] = value

    def __delitem__(self, name):
        del self.sub_resources[name]


class StaticFileResource(Resource):
    def __init__(self, path, cache_max_age=60*60*24*365*10): # 10 years in seconds
        Resource.__init__(self)
        self.path = path
        self.cache_max_age = cache_max_age

    def get(self, request, v=None):
        if not os.path.exists(self.path):
            return HTTPNotFoundResponse()
        if not os.path.isfile(self.path):
            return HTTPForbiddenResponse(entity='%s is not a file' % self.path)

        # Don't send the result if the content has not been modified since the If-Modified-Since
        modified = os.stat(self.path).st_mtime
        if 'If-Modified-Since' in request.headers and time.mktime(email.utils.parsedate(request.headers['If-Modified-Since'])) >= modified:
            return HTTPNotModifiedResponse()

        headers = {'Last-Modified': str(email.utils.formatdate(modified))}

        mimetype = mimetypes.guess_type(self.path)[0]
        if mimetype:
            headers['Content-Type'] = mimetype

        cache_time = self.cache_max_age if v else 0
        if cache_time > 0:
            headers['Expires'] = str(datetime.datetime.utcnow() + datetime.timedelta(seconds=cache_time))
            headers['Cache-Control'] = 'max-age=' + str(cache_time)
        else:
            headers['Cache-Control'] = 'public'

        if request.method == 'HEAD':
            entity = ''
        else:
            file = open(self.path, 'rb')
            try:
                entity = file.read()
            finally:
                file.close()

        return HTTPResponse(entity=entity, headers=headers)


class StaticDirectoryResource(StaticFileResource):
    def __getitem__(self, name):
        if not os.path.isdir(self.path):
            return HTTPForbiddenResponse(entity='%s is not a directory' % self.path)
        return StaticDirectoryResource(os.path.join(self.path, name))


class JSONResource(DictResource):
    def __getitem__(self, name):
        return JSONResource(DictResource.__getitem__(self, name if not isinstance(self.sub_resources, list) else int(name)))

    def get(self, request, callback=None):
        response = HTTPResponse(entity=json.dumps(self.sub_resources))
        if callback is not None:
            response.entity = callback+'('+response.entity+');'
            response.headers['Content-Type'] = 'application/json-p'
        return response


class TraceResource(Resource):
    def trace(self, request, **kwargs):
        return str(request) # FIXME


class LazyDictResource(DictResource):
    def __init__(self, lazy_resources=None):
        self.lazy_resources = lazy_resources or {}

    def __getitem__(self, name):
        if name not in self.sub_resources:
            value = self.lazy_resources[name]()
            self.sub_resources[name] = value
            return value
        return DictResource.__getitem__(self, name)
