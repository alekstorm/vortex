import httplib

from vortex import HTTPResponse

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

