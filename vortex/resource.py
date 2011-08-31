import datetime
import email.utils
import inspect
import json
import mimetypes
import os.path
import time

from vortex.response import *

class Resource(object):
    SUPPORTED_METHODS = set(['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE'])

    def __init__(self):
        self.supported_methods = [method for method in self.SUPPORTED_METHODS if hasattr(self, method.lower())]

    def __call__(self, request):
        kwargs = dict([(key, value[0]) for key, value in request.arguments.iteritems()])
        if request.method in self.supported_methods:
            method_name = request.method.lower()
        elif request.method == 'HEAD' and 'GET' in self.supported_methods:
            method_name = 'get'
        elif request.method.upper() in self.SUPPORTED_METHODS:
            return HTTPMethodNotAllowedResponse(allowed=self.supported_methods)
        else:
            return HTTPNotImplementedResponse()

        method = getattr(self, method_name)
        try:
            return method(request, **kwargs)
        except TypeError as err:
            argspec = inspect.getargspec(method)
            args = argspec.args[2:]
            keywords = set(kwargs.keys())
            missing = set(args[:-len(argspec.defaults)] if argspec.defaults else args) - keywords
            if len(missing) > 0:
                return HTTPBadRequestResponse(entity='Missing arguments: '+' '.join(missing))
            invalid = keywords - set(args)
            if not argspec.keywords and len(invalid) > 0:
                return HTTPBadRequestResponse(entity='Unexpected arguments: '+' '.join(invalid))
            raise


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
    CACHE_MAX_AGE = 60*60*24*365*10 # 10 years in seconds

    def __init__(self, path):
        Resource.__init__(self)
        self.path = path

    def head(self, request, **kwargs):
        return self.get(request, **kwargs)

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

        mimetype, encoding = mimetypes.guess_type(self.path)
        if mimetype:
            headers['Content-Type'] = mimetype

        cache_time = self.CACHE_MAX_AGE if v else 0

        if cache_time > 0:
            headers['Expires'] = str(datetime.datetime.utcnow() + datetime.timedelta(seconds=cache_time))
            headers['Cache-Control'] = 'max-age=' + str(cache_time)
        else:
            headers['Cache-Control'] = 'public'

        if request.method == 'HEAD':
            return HTTPResponse(headers=headers)

        file = open(self.path, 'rb')
        try:
            contents = HTTPResponse(entity=file.read(), headers=headers)
        finally:
            file.close()
        return contents


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


class LazyResource(Resource):
    def __init__(self, lazy_resources=None):
        self.lazy_resources = lazy_resources or {}
        self.loaded_resources = {}

    def __getitem__(self, name):
        if name not in self.loaded_resources:
            value = self.lazy_resources[name]()
            self.loaded_resources[name] = value
        else:
            value = self.loaded_resources[name]
        return value
