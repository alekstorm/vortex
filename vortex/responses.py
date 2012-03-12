import httplib

from vortex import HTTPPreamble, HTTPResponse

class HTTPCreatedResponse(HTTPResponse):
    def __init__(self, **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.CREATED, **kwargs))


class HTTPNoContentResponse(HTTPResponse):
    def __init__(self, **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NO_CONTENT, **kwargs))


class HTTPFoundResponse(HTTPResponse):
    def __init__(self, location, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.FOUND, headers={'Location': location}, **kwargs), body=body)


class HTTPNotModifiedResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_MODIFIED, **kwargs), body=body)


class HTTPNotFoundResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_FOUND, **kwargs), body=body)


class HTTPBadRequestResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.BAD_REQUEST, **kwargs), body=body)


class HTTPUnauthorizedResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.UNAUTHORIZED, **kwargs), body=body)


class HTTPForbiddenResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.FORBIDDEN, **kwargs), body=body)


class HTTPMethodNotAllowedResponse(HTTPResponse):
    def __init__(self, allowed, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.METHOD_NOT_ALLOWED, headers={'Allowed': allowed}, **kwargs), body=body)


class HTTPNotImplementedResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_IMPLEMENTED, **kwargs), body=body)


class HTTPInternalServerErrorResponse(HTTPResponse):
    def __init__(self, body='', **kwargs):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.INTERNAL_SERVER_ERROR, **kwargs), body=body)
