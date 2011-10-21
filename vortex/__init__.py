import Cookie
import collections
import hashlib
import httplib
import inspect
import json
import logging
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from   tornado.escape import utf8
import tornado.web
import traceback
import urllib
from   xml.etree.ElementTree import Element, ElementTree, iselement

logger = logging.getLogger('vortex')

SAFE_METHODS = set(('GET', 'HEAD'))

def add_slash(call):
    def wrap(self, request, *args, **kwargs):
        return self[''](request, *args, **kwargs)
    return wrap

def remove_slash(getitem):
    def wrap(self, name):
        if len(name) == 0:
            return self
        return getitem(self, name)
    return wrap

def json2xml(data):
    def convert_elem(data, tag='item'):
        root = Element(tag)
        if isinstance(data, dict):
            for key, val in data.iteritems():
                if isinstance(val, dict) or isinstance(val, list):
                    root.append(convert_elem(val, key))
                else:
                    root.set(key, str(val))
        elif isinstance(data, list):
            for item in data:
                root.append(convert_elem(item))
        else:
            root.set('_value', str(data))
        return root

    return lambda request: convert_elem(data, 'root')

def format(handlers, default=None, unknown=None):
    def wrap1(getitem):
        def wrap2(self, name):
            parts = name.split('.')
            resource = getitem(self, parts[0])
            if len(parts) > 1:
                handler = handlers.get(parts[1], None)
                if handler:
                    return handler(resource)
                if unknown:
                    return unknown(resource)
                raise KeyError()
            if default:
                return default(resource)
            raise KeyError()
        return wrap2
    return wrap1

def authenticate(retrieve, cookie_name, redirect=None, unauthorized=None):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            cookie = request.cookies.get(cookie_name, None)
            if cookie is not None:
                user = retrieve(self, cookie)
                if user is not None:
                    return fn(self, request, user, *args, **kwargs)
            if redirect and request.method in SAFE_METHODS:
                return HTTPResponse(httplib.FOUND, headers={'Location': redirect})
            return unauthorized(request) if unauthorized else HTTPUnauthorizedResponse()
        return wrap2
    return wrap1

def xsrf(cookie):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            if request.method not in SAFE_METHODS and ('_xsrf' not in kwargs or cookie not in request.cookies or kwargs.pop('_xsrf') != request.cookies[cookie].value):
                return HTTPResponse(httplib.FORBIDDEN, entity='XSRF cookie does not match request argument')
            return fn(self, request, *args, **kwargs)
        return wrap2
    return wrap1

def signed_cookie(secret):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            for key, cookie in request.cookies.items():
                value = tornado.web.decode_signed_value(secret, cookie.key, cookie.value)
                if value is None:
                    del request.cookies[key]
                else:
                    cookie.set(key, value, value)
            response = fn(self, request)
            for key, cookie in getattr(response, 'cookies', {}).iteritems():
                value = tornado.web.create_signed_value(secret, key, unicode(cookie.value))
                cookie.set(key, value, value)
                cookie['path'] = '/'
            return response
        return wrap2
    return wrap1

def coerce_response(response):
    if response is None:
        response = HTTPResponse(httplib.NO_CONTENT)
    elif isinstance(response, basestring):
        response = HTTPResponse(entity=response)
    elif isinstance(response, dict):
        response = HTTPResponse(entity=json.dumps(response), headers={'Content-Type': 'application/json'})
    elif iselement(response):
        xml = StringIO.StringIO()
        ElementTree(response).write(xml)
        response = HTTPResponse(entity=xml.getvalue(), headers={'Content-Type': 'application/xml'})
    return response


class Resource(object):
    SUPPORTED_METHODS = set(('OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE'))

    def __call__(self, request, *args):
        try:
            method_name = request.method.lower()
            if request.method in self.SUPPORTED_METHODS:
                method = getattr(self, method_name)
            else:
                return HTTPResponse(httplib.NOT_IMPLEMENTED)
        except AttributeError:
            if not hasattr(self, method_name):
                get_method = getattr(self, 'get', None)
                if request.method == 'HEAD' and get_method is not None:
                    method = get_method
                else:
                    return HTTPResponse(httplib.METHOD_NOT_ALLOWED, headers={'Allowed': [method for method in self.SUPPORTED_METHODS if hasattr(self, method.lower())]})
            else:
                raise

        kwargs = dict([(key, value[0]) for key, value in request.arguments.iteritems()])
        try:
            return method(request, *args, **kwargs)
        except TypeError as err:
            argspec = inspect.getargspec(method)
            args = argspec.args[2:]
            keywords = set(kwargs.keys())
            missing = set(args[:-len(argspec.defaults)] if argspec.defaults else args) - keywords
            if len(missing) > 0:
                return HTTPResponse(httplib.BAD_REQUEST, entity='Missing arguments: '+' '.join(missing))
            invalid = keywords - set(args)
            if not argspec.keywords and len(invalid) > 0:
                return HTTPResponse(httplib.BAD_REQUEST, entity='Unexpected arguments: '+' '.join(invalid))
            raise


class HTTPResponse(object):
    def __init__(self, status_code=httplib.OK, reason=None, version='HTTP/1.1', headers=None, cookies=None):
        self.status_code = status_code
        self.reason = reason
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
        self.headers.setdefault('Content-Type', 'text/html')
        for name, values in self.headers.iteritems():
            lines.extend([utf8(name) + b': ' + utf8(value) for value in (values if isinstance(values, list) else [values])])
        lines.extend([str(cookie) for cookie in self.cookies.itervalues()])
        return b'\r\n'.join(lines) + b'\r\n\r\n'


class HTTPStream(object):
    def __init__(self, response=None, etag=True):
        self.headers_written = False
        self.finished = False
        self.etag = etag
        self._chunked = False
        self._headers_buffer = None
        self._headers_listener = None
        self._body_listener = None
        self._body_buffer = collections.deque()
        self._finish_listener = None

        if headers:
            self.write(coerce_response(headers))

    def listen(self, headers_listener, body_listener, finish_listener):
        self._headers_listener = headers_listener
        self._body_listener = body_listener
        self._finish_listener = finish_listener

    def write(self, data=''):
        if not self.headers_written:
            if self._headers_listener:
                if self._headers_buffer:
                    headers = self._headers_buffer
                else:
                    headers = data
                if headers:
                    data = headers.entity + data
                    if self.finished:
                        body = ''.join(self._body_buffer) + data
                        headers.headers.setdefault('Content-Length', str(len(body)))
                        self._body_buffer = collections.deque((body,))
                        data = ''
                    else:
                        headers.headers.setdefault('Transfer-Encoding', 'chunked')
                        self._chunked = True

                    self._headers_listener(headers)
                    self.headers_written = True
            else:
                self._headers_buffer = data
                data = ''
        body_writer = HTTPBodyStream()
        if len(data) > 0: # without this, calling ``write('')`` would terminate a chunked response
            self._body_buffer.append(data)
        if self._body_listener:
            while self._body_buffer:
                body = self._body_buffer.popleft()
                if self._chunked:
                    body = hex(len(body))[2:] + '\r\n' + body
                self._body_listener(body+'\r\n')

    def finish(self):
        self.finished = True
        self._body_buffer.append('')
        self.write()
        if self._finish_listener:
            self._finish_listener()


class Application(object):
    def __init__(self, root=None):
        self.root = root

    def __call__(self, request):
        try:
            resource = self.root
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
                    response = HTTPResponse(httplib.NOT_FOUND)
                    break
            if response is None:
                response = resource(request) if hasattr(resource, '__call__') else HTTPResponse(httplib.METHOD_NOT_ALLOWED)
        except:
            response = HTTPResponse(httplib.INTERNAL_SERVER_ERROR, entity=traceback.format_exc())

        finished = not hasattr(response, 'write')
        stream = HTTPStream(response) if finished else response

        def write_headers(headers):
            if headers.status_code >= 400:
                logger.log(logging.ERROR if headers.status_code >= 500 else logging.WARNING, '%s\n%s', str(request), str(headers))

            if stream.finished and headers.status_code == httplib.OK and request.method in SAFE_METHODS:
                etag = hashlib.sha1(headers.entity).hexdigest()
                inm = request.headers.get('If-None-Match')
                if inm and inm.find(etag) != -1:
                    headers = HTTPResponse(httplib.NOT_MODIFIED)
                else:
                    headers.headers.setdefault('Etag', etag)

            request.write(headers.headers_str())

        stream.listen(write_headers, lambda body: request.write(body), lambda: request.finish())

        if finished:
            stream.finish()


class VirtualHost(object):
    def __init__(self, hosts, default=None):
        self.hosts = hosts
        self.default = default

    def __call__(self, request):
        host_val = request.headers.get('Host')
        if host_val:
            hostname = host_val.split(':')[0]
            host = self.hosts.get(request, hostname)
            if host:
                return host(request)
        return self.default(request) if self.default else HTTPResponse(httplib.BAD_REQUEST, 'Virtual host not found')
