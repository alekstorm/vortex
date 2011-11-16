try:
    import BytesIO
except ImportError:
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO
import Cookie
import collections
from   email.utils import formatdate
from   gzip import GzipFile
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

def xsrf_form_html(cookie):
    return r'''<script language="javascript">var r=document.cookie.match('\\b%s=([^;]*)\\b');document.write("<input type=\"hidden\" name=\"_xsrf\" value=\""+(r?r[1]:'')+"\" />");</script>''' % cookie

def signed_cookie(secret):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            for key, cookie in request.cookies.items():
                value = tornado.web.decode_signed_value(secret, cookie.key, cookie.value)
                if value is None:
                    del request.cookies[key]
                else:
                    cookie.set(key, value, value)
            response = fn(self, request, *args, **kwargs)
            for key, cookie in getattr(response, 'cookies', {}).iteritems():
                value = tornado.web.create_signed_value(secret, key, unicode(cookie.value))
                cookie.set(key, value, value)
                cookie['path'] = '/'
            return response
        return wrap2
    return wrap1

def coerce_response(response):
    if isinstance(response, basestring):
        response = HTTPResponse(entity=response, headers={'Content-Type': 'text/html'})
    elif isinstance(response, dict):
        response = HTTPResponse(entity=json.dumps(response), headers={'Content-Type': 'application/json'})
    elif iselement(response):
        xml = StringIO()
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
    def __init__(self, status_code=httplib.OK, reason=None, version='HTTP/1.1', entity='', headers=None, cookies=None):
        self.status_code = status_code
        self.reason = reason
        self.version = version
        self.entity = entity
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
        for name, values in self.headers.iteritems():
            lines.extend([utf8(name) + b': ' + utf8(value) for value in (values if isinstance(values, list) else [values])])
        lines.extend([str(cookie) for cookie in self.cookies.itervalues()])
        return b'\r\n'.join(lines) + b'\r\n\r\n'


class _GzipEncoder(object):
    def __init__(self, request, response):
        response.headers['Vary'] = response.headers.get('Vary', '') + ',Accept-Encoding'
        self._accepted = 'gzip' in request.headers.get('Accept-Encoding', '').replace(' ','').split(',')
        if self._accepted:
            self._value = BytesIO()
            self._file = GzipFile(mode='wb', fileobj=self._value)
            response.headers['Content-Encoding'] = response.headers.get('Content-Encoding', '') + ',gzip'

    def encode(self, data):
        if self._accepted:
            self._file.write(data)
            self._file.flush()
            data = self._value.getvalue()
            self._value.truncate(0)
            self._value.seek(0)
        return data

    def finish(self, data):
        if self._accepted:
            data = self.encode(data)
            self._file.close()
        return data


class HTTPStream(object):
    def __init__(self, request, response, encoders=[_GzipEncoder]):
        self._request = request
        self._response = response
        self._buffer = []
        self._headers_written = False
        self._finished = False
        self._chunked = False
        self._encoders = [encoder(request, response) for encoder in encoders]
        self._response.headers.setdefault('Date', formatdate(timeval=None, localtime=False, usegmt=True))
        self.write(response.entity)

    def write(self, data):
        self._buffer.append(data)

    def _write_headers(self):
        self._request.write(str(self._response))
        self._headers_written = True

    def flush(self, data=''):
        if self._finished:
            raise RuntimeError('Cannot flush a finished stream')
        self.write(data)
        if not self._headers_written:
            self._response.headers.setdefault('Transfer-Encoding', 'chunked')
            self._write_headers()
            self._chunked = True
        self._flush_body(self._encode_body())

    def _encode_body(self):
        body = ''.join(self._buffer)
        for encoder in self._encoders:
            body = encoder.encode(body)
        return body

    def _flush_body(self, body):
        del self._buffer[:]
        len_body = len(body)
        if len_body > 0:
            if self._chunked:
                self._request.write(hex(len_body)[2:]+'\r\n')
                body += '\r\n'
            self._request.write(body)

    def finish(self, data=''):
        self.write(data)
        body = self._encode_body()
        final = ''
        for encoder in self._encoders:
            final = encoder.finish(final)
        body += final
        if not self._headers_written:
            self._response.headers.setdefault('Content-Length', str(len(body)))
            etag = self._response.headers.setdefault('Etag', '"%s"' % hashlib.sha1(body).hexdigest())
            inm = self._request.headers.get('If-None-Match', '')
            if inm and 200 <= self._response.status_code < 300:
                if self._request.method not in SAFE_METHODS:
                    self._response.status_code = httplib.PRECONDITION_FAILED
                elif inm.find(etag) != -1 or inm == '*':
                    self._response.status_code = httplib.NOT_MODIFIED
                body = ''
            self._write_headers()
        self._flush_body(body)
        if self._chunked:
            self._request.write('0\r\n\r\n')
        self._request.finish()
        self._finished = True


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
                response = coerce_response(resource(request)) if hasattr(resource, '__call__') else HTTPResponse(httplib.METHOD_NOT_ALLOWED)
        except:
            response = HTTPResponse(httplib.INTERNAL_SERVER_ERROR, entity=traceback.format_exc())

        if response:
            if response.status_code >= 400:
                logger.log(logging.ERROR if response.status_code >= 500 else logging.WARNING, '%s\n%s', str(request), str(response))

            HTTPStream(request, response).finish()


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
