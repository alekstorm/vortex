import Cookie
import datetime
import email.utils
import hashlib
import httplib
import inspect
import json
import mimetypes
import os.path
import time
from   tornado.escape import utf8
import traceback
import urllib

SAFE_METHODS = ('GET', 'HEAD')

class HTTPResponse(object):
    def __init__(self, status_code=httplib.OK, reason=None, entity='', version='HTTP/1.1', headers=None, cookies=None):
        self.status_code = status_code
        self.reason = reason
        self.entity = entity
        self.version = version
        self.headers = headers or {}
        self.cookies = Cookie.SimpleCookie()
        for key, value in (cookies or {}).iteritems():
            if isinstance(value, dict):
                self.cookies[key] = value['value']
                for name, morsel_attr in value:
                    self.cookies[key][name] = morsel_attr
            else:
                self.cookies[key] = value

    def __str__(self):
        lines = [utf8(self.version + b' ' + str(self.status_code) + b' ' + (self.reason or httplib.responses[self.status_code]))]
        self.headers.setdefault('Content-Length', str(len(self.entity)))
        self.headers.setdefault('Content-Type', 'text/html')
        for name, values in self.headers.iteritems():
            lines.extend([utf8(name) + b': ' + utf8(value) for value in (values if isinstance(values, list) else [values])])
        for cookie in self.cookies.itervalues():
            lines.append(str(cookie))
        return b'\r\n'.join(lines) + b'\r\n\r\n' + self.entity


class HTTPNoContentResponse(HTTPResponse):
    def __init__(self, cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.NO_CONTENT, cookies=cookies)


class HTTPFoundResponse(HTTPResponse):
    def __init__(self, location, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.FOUND, headers={'Location': location}, entity=entity, cookies=cookies)


class HTTPNotModifiedResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.NOT_MODIFIED, entity=entity, cookies=cookies)


class HTTPNotFoundResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.NOT_FOUND, entity=entity, cookies=cookies)


class HTTPBadRequestResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.BAD_REQUEST, entity=entity, cookies=cookies)


class HTTPUnauthorizedResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.UNAUTHORIZED, entity=entity, cookies=cookies)


class HTTPForbiddenResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.FORBIDDEN, entity=entity, cookies=cookies)


class HTTPMethodNotAllowedResponse(HTTPResponse):
    def __init__(self, allowed, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.METHOD_NOT_ALLOWED, headers={'Allowed': allowed}, entity=entity, cookies=cookies)


class HTTPNotImplementedResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.NOT_IMPLEMENTED, entity=entity, cookies=cookies)


class HTTPInternalServerErrorResponse(HTTPResponse):
    def __init__(self, entity='', cookies=None):
        HTTPResponse.__init__(self, status_code=httplib.INTERNAL_SERVER_ERROR, entity=entity, cookies=cookies)


class Resource(object):
    SUPPORTED_METHODS = ['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE']

    def __init__(self, sub_resources=None):
        self.supported_methods = [method for method in self.SUPPORTED_METHODS if hasattr(self, method.lower())]
        self.sub_resources = sub_resources or {}

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

    def __getitem__(self, name):
        return self.sub_resources[name]


class MutableResource(Resource):
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
            return HTTPForbiddenResponse(entity='%s is not a directory' % path)
        return StaticDirectoryResource(os.path.join(self.path, name))


class JSONResource(Resource):
    def __getitem__(self, name):
        return JSONResource(Resource.__getitem__(self, name if not isinstance(self.sub_resources, list) else int(name)))

    def get(self, request):
        return json.dumps(self.sub_resources)


class TraceResource(Resource):
    def trace(self, request, **kwargs):
        return str(request) # FIXME


class Application(object):
    def __init__(self, resource=None):
        self.resource = resource

    def __call__(self, request):
        try:
            resource = self.resource
            response = None
            for part in request.path.split('/')[1:]:
                not_found = False
                if resource is not None and hasattr(resource, '__getitem__'):
                    try:
                        resource = resource[urllib.unquote(part)]
                    except KeyError:
                        not_found = True
                else:
                    not_found = True
                if not_found:
                    response = HTTPNotFoundResponse()
                    break
            if response is None:
                response = resource(request) if hasattr(resource, '__call__') else HTTPMethodNotAllowedResponse(allowed=[])
                if response is None:
                    response = HTTPNoContentResponse()
                elif isinstance(response, basestring):
                    response = HTTPResponse(entity=response)
                elif isinstance(response, dict):
                    response = HTTPResponse(entity=json.dumps(response))
                    response.headers.setdefault('Content-Type', 'application/json')

                if response.status_code == httplib.OK and request.method in SAFE_METHODS:
                    etag = hashlib.sha1(response.entity).hexdigest()
                    inm = request.headers.get('If-None-Match')
                    if inm and inm.find(etag) != -1:
                        response = HTTPNotModifiedResponse()
                    else:
                        response.headers.setdefault('Etag', etag)

                if request.method == 'HEAD':
                    response.entity = ''
        except:
            response = HTTPInternalServerErrorResponse(entity=traceback.format_exc())
        if response.status_code in (httplib.INTERNAL_SERVER_ERROR, httplib.BAD_REQUEST):
            print str(response)
        request.write(str(response))
        request.finish()
        return response
