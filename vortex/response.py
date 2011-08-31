import Cookie
import httplib
from   tornado.escape import utf8

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

