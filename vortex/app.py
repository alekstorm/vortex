import hashlib
import httplib
import json
import logging
import tornado.web
import traceback
import urllib

from vortex.response import *

logger = logging.getLogger('vortex')

def authenticate(retrieve, cookie_name, redirect=None, unauthorized=None):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            cookie = request.cookies.get(cookie_name, None)
            if cookie is not None:
                user = retrieve(cookie)
                if user is not None:
                    return fn(self, request, user, *args, **kwargs)
            if redirect and request.method in SAFE_METHODS:
                return HTTPFoundResponse(redirect)
            return unauthorized(request) if unauthorized else HTTPUnauthorizedResponse()
        return wrap2
    return wrap1

def xsrf(cookie):
    def wrap1(fn):
        def wrap2(self, request, *args, **kwargs):
            if request.method not in SAFE_METHODS and ('_xsrf' not in kwargs or cookie not in request.cookies or kwargs.pop('_xsrf') != request.cookies[cookie].value):
                return HTTPForbiddenResponse(entity='XSRF cookie does not match request argument')
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
        response = HTTPNoContentResponse()
    elif isinstance(response, basestring):
        response = HTTPResponse(entity=response)
    elif isinstance(response, dict):
        response = HTTPResponse(entity=json.dumps(response))
        response.headers.setdefault('Content-Type', 'application/json')
    return response


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
                    response = HTTPNotFoundResponse()
                    break
            if response is None:
                response = coerce_response(resource(request)) if hasattr(resource, '__call__') else HTTPMethodNotAllowedResponse(allowed=[])

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
        if response.status_code >= 500: # TODO print request
            logger.error(str(response))
        elif response.status_code >= 400:
            logger.warning(str(response))
        request.write(str(response))
        request.finish()
        return response
