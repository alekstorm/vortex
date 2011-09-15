import logging
from   memcache import Client
import time
from   tornado.httpserver import HTTPServer
from   tornado.ioloop import IOLoop

from   vortex.app import *
from   vortex.memcached import Memcacher, memcached
from   vortex.resource import *

logging.getLogger('vortex').addHandler(logging.StreamHandler())

class ArgResource(Resource):
    def get(self, request, a, b='default'):
        return 'Success: a=%s, b=%s' % (a, b)

@memcached
class MemcachedResource(Resource):
    def __getitem__(self, name):
        return MemcachedSubResource()

class MemcachedSubResource(Resource):
    def __init__(self):
        time.sleep(2)
        self.expensive = 'This took a long time to compute'

    def get(self, request):
        return self.expensive

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

app = Application(Memcacher(Client(['127.0.0.1:11211']), {
    '': lambda request: 'Hello World!',
    'static': StaticDirectoryResource(os.path.join(os.path.dirname(__file__), 'static')),
    'json': JSONResource({'a': ['b', 1], 'c': {'d': True}}),
    'args': ArgResource(),
    'memcached': MemcachedResource(),
    'auth': {
        'login': LoginResource(),
        'secret': SecretResource(),
        'logout': LogoutResource(),
    },
}))
HTTPServer(app).listen(port=3000)
IOLoop.instance().start()
