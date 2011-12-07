import httplib

from vortex import HTTPPreamble, HTTPResponse

class HTTPCreatedResponse(HTTPResponse):
    def __init__(self, cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.CREATED, cookies=cookies))


class HTTPNoContentResponse(HTTPResponse):
    def __init__(self, cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NO_CONTENT, cookies=cookies))


class HTTPFoundResponse(HTTPResponse):
    def __init__(self, location, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.FOUND, headers={'Location': location}, cookies=cookies), body=body)


class HTTPNotModifiedResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_MODIFIED, cookies=cookies), body=body)


class HTTPNotFoundResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_FOUND, cookies=cookies), body=body)


class HTTPBadRequestResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.BAD_REQUEST, cookies=cookies), body=body)


class HTTPUnauthorizedResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.UNAUTHORIZED, cookies=cookies), body=body)


class HTTPForbiddenResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.FORBIDDEN, cookies=cookies), body=body)


class HTTPMethodNotAllowedResponse(HTTPResponse):
    def __init__(self, allowed, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.METHOD_NOT_ALLOWED, headers={'Allowed': allowed}, cookies=cookies), body=body)


class HTTPNotImplementedResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.NOT_IMPLEMENTED, cookies=cookies), body=body)


class HTTPInternalServerErrorResponse(HTTPResponse):
    def __init__(self, body='', cookies=None):
        HTTPResponse.__init__(self, HTTPPreamble(status_code=httplib.INTERNAL_SERVER_ERROR, cookies=cookies), body=body)
