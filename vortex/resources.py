import datetime
import email.utils
import hashlib
import httplib
import json
import mimetypes
import os.path
import time
import uuid

from vortex import SAFE_METHODS, HTTPStream, Resource, authenticate, http_date, signed_cookie, xsrf
from vortex.responses import *

class DictResource(Resource):
    def __init__(self, sub_resources=None):
        Resource.__init__(self)
        self.sub_resources = sub_resources or {}

    def __getitem__(self, name):
        return self.sub_resources[name]

    def __contains__(self, name):
        return name in self.sub_resources


class MutableDictResource(DictResource):
    def __setitem__(self, name, value):
        self.sub_resources[name] = value

    def __delitem__(self, name):
        del self.sub_resources[name]


class UploadResource(MutableDictResource):
    class ContentResource(Resource):
        def __init__(self, uploader, name, content):
            self.uploader = uploader
            self.name = name
            self.content = content

        def get(self, request):
            return self.content

        def put(self, request):
            self.content = request.body
            return HTTPNoContentResponse()

        def delete(self, request):
            del self.uploader[self.name]
            return HTTPNoContentResponse()

    def __getitem__(self, name):
        def put(request):
            if request.method != 'PUT':
                return HTTPNotFoundResponse()
            self[name] = self.ContentResource(self, name, request.body)
            return HTTPCreatedResponse()

        return self.sub_resources.get(name, put)


class StaticFileResource(Resource):
    def __init__(self, path, os=os, open=open,
                 chunk_size=64*2**10,            # 64kB
                 cache_max_age=60*60*24*365*10): # 10 years in seconds
        Resource.__init__(self)
        self.path = path
        self.os = os
        self.open = open
        self.chunk_size = chunk_size
        self.cache_max_age = cache_max_age

    def get(self, request, **kwargs):
        if not self.os.path.exists(self.path):
            return HTTPNotFoundResponse()
        if not self.os.path.isfile(self.path):
            return HTTPMethodNotAllowedResponse(allowed=[])

        # Don't send the result if the content has not been modified since the If-Modified-Since
        modified = self.os.stat(self.path).st_mtime

        request_range = request.headers.get('Range')

        status_code = httplib.OK
        headers = {
            'Accept-Ranges': 'bytes',
            'Etag': '"%s"' % hashlib.sha1('\0'.join([self.path, str(modified)])).hexdigest(),
            'Last-Modified': http_date(modified),
        }

        if 'If-Modified-Since' in request.headers and time.mktime(email.utils.parsedate(request.headers['If-Modified-Since'])) >= modified:
            return HTTPNotModifiedResponse(headers=headers)

        inm = request.headers.get('If-None-Match', None)
        if inm:
            if request.method not in SAFE_METHODS:
                return HTTPPreconditionFailedResponse()
            elif inm.find(headers['Etag']) != -1 or inm == '*':
                return HTTPNotModifiedResponse(headers=headers)

        mimetype = mimetypes.guess_type(self.path)[0]
        if mimetype:
            headers['Content-Type'] = mimetype

        cache_time = self.cache_max_age if len(kwargs) > 0 else 0
        if cache_time > 0:
            headers['Expires'] = http_date(time.mktime((datetime.datetime.utcnow() + datetime.timedelta(seconds=cache_time)).timetuple()))
            headers['Cache-Control'] = 'max-age=' + str(cache_time)

        # FIXME multiple ranges
        body_range = [0, None]
        if request_range is not None:
            body_range = [(int(num) if len(num) > 0 else None) for num in request_range.split('bytes=')[1].split('-')]

        file_size = os.path.getsize(self.path)
        if body_range[0] is None:
            body_range = [file_size-body_range[1], file_size-1]
        elif body_range[1] is None:
            body_range[1] = file_size-1
        if request_range is not None:
            status_code = httplib.PARTIAL_CONTENT
            headers['Content-Range'] = 'bytes %i-%i/%i' % (body_range[0], body_range[1], file_size)

        response = HTTPPreamble(status_code=status_code, headers=headers)

        if request.method == 'HEAD':
            return response

        stream = HTTPStream(request, response)
        size = body_range[1] - body_range[0] + 1
        file = self.open(self.path, 'rb')
        file.seek(body_range[0])
        try:
            while True:
                chunk_size = min(self.chunk_size, size)
                size -= chunk_size
                chunk = file.read(chunk_size)
                if len(chunk) == 0:
                    break
                stream.write(chunk)
        finally:
            file.close()

        stream.finish()

    def __getitem__(self, name):
        if not self.os.path.isdir(self.path):
            raise KeyError()
        return self.__class__(self.os.path.join(self.path, name))


class JSONResource(DictResource):
    def __getitem__(self, name):
        return JSONResource(DictResource.__getitem__(self, name if not isinstance(self.sub_resources, list) else int(name)))

    def get(self, request, callback=None):
        response = HTTPOkResponse(body=json.dumps(self.sub_resources))
        if callback is not None:
            response.body = callback+'('+response.entity+');'
            response.preamble.headers['Content-Type'] = 'application/json-p'
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


class ParentResource(Resource):
    def __init__(self, delegate, **data):
        self.delegate = delegate
        self.data = data

    def __getitem__(self, name):
        return self.delegate(name)


class SocketIOResource(Resource):
    def __init__(self, flash_policy_port=843, flash_policy_file=None):
        self.flash_policy_port = flash_policy_port
        self.flash_policy_file = flash_policy_file

    def __getitem__(self, name):
        return 
