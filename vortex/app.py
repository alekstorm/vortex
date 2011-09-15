import hashlib
import httplib
import json
import traceback
import urllib

from vortex.response import *

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
