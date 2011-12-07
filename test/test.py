from   datetime import timedelta
import logging
from   memcache import Client
import os
import time
from   tornado.httpserver import HTTPServer
from   tornado.ioloop import IOLoop
from   tornado.template import Loader
import uuid

from   vortex import Application, HTTPResponse, HTTPStream, Resource, authenticate, signed_cookie, xsrf
from   vortex.resources import DictResource, JSONResource, StaticDirectoryResource, StaticFileResource, UploadResource

class ArgResource(Resource):
    def get(self, request, a, b='default'):
        return 'Success: a=%s, b=%s' % (a, b)

COOKIE_SECRET = str(uuid.uuid4())

class AppResource(Resource):
    users = {}

    @signed_cookie(COOKIE_SECRET)
    @xsrf('user')
    @authenticate(lambda user: AppResource.users.get(user.value, None), 'user', redirect='/auth/login')
    def __call__(self, *args):
        return Resource.__call__(self, *args)

class LoginResource(Resource):
    @signed_cookie(COOKIE_SECRET)
    def get(self, request):
        user = str(uuid.uuid4())
        AppResource.users[user] = user
        return HTTPResponse(entity='Your username is: '+user, cookies={'user': user})

class SecretResource(AppResource):
    def get(self, request, user):
        return 'Hello, '+user

    def post(self, request, user):
        return 'Done'

class LogoutResource(AppResource):
    def get(self, request, user):
        return HTTPResponse(entity='Bye, '+user, cookies={'user': ''})

class UploadFormResource(UploadResource):
    def __init__(self, loader):
        UploadResource.__init__(self)
        self.loader = loader

    def get(self, request):
        return self.loader.load('upload.html').generate(items=self.sub_resources.keys())

class AsyncResource(Resource):
    def get(self, request):
        def callback():
            response.write('This was asynchronous')
            response.finish()
        response = HTTPStream(HTTPResponse())
        IOLoop.instance().add_timeout(timedelta(seconds=2), callback)
        return response


logging.getLogger('vortex').addHandler(logging.StreamHandler())

static_dir = os.path.join(os.path.dirname(__file__), 'static')
loader = Loader(os.path.join(os.path.dirname(__file__), 'template'))

app = Application({
    '': lambda request: 'Hello World!',
    'static': StaticDirectoryResource(static_dir),
    'favicon.ico': StaticFileResource(os.path.join(static_dir, 'favicon.ico')),
    'json': JSONResource({'a': ['b', 1], 'c': {'d': True}}),
    'args': ArgResource(),
    'auth': {
        'login': LoginResource(),
        'secret': SecretResource(),
        'logout': LogoutResource(),
    },
    'async': AsyncResource(),
    'upload': UploadFormResource(loader),
})
HTTPServer(app).listen(port=3000)
IOLoop.instance().start()
