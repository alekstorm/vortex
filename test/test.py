from   datetime import timedelta
import logging
from   memcache import Client
import os
import time
from   tornado.httpserver import HTTPServer
from   tornado.ioloop import IOLoop
import uuid

from   vortex import Application, HTTPResponse, HTTPStream, Resource, authenticate, add_slash, format, json2xml, remove_slash, signed_cookie, xsrf
from   vortex.memcached import Memcacher, memcached
from   vortex.resources import DictResource, JSONResource, StaticDirectoryResource, StaticFileResource

logging.getLogger('vortex').addHandler(logging.StreamHandler())

class ArgResource(Resource):
    def get(self, request, a, b='default'):
        return 'Success: a=%s, b=%s' % (a, b)

@memcached
class MemcachedResource(Resource):
    def __getitem__(self, name):
        return ExpensiveResource()

class NonMemcachedResource(Resource):
    def __getitem__(self, name):
        return ExpensiveResource()

class ExpensiveResource(Resource):
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

class FormatResource(Resource):
    @format({'json': lambda r: JSONResource(r), 'xml': json2xml})
    def __getitem__(self, name):
        return {'name': 'Guido', 'interests': [{'title': 'python', 'level': 9}, {'title': 'dancing', 'level': 5}], 'books': ['Python Tutorial', 'Python Reference Manual'], 'address': {'city': 'Mountain View', 'state': 'CA'}}

class AddSlashResource(DictResource):
    def __init__(self):
        DictResource.__init__(self, {'': lambda request: 'Slash added'})

    @add_slash
    def __call__(self, request): pass

class RemoveSlashResource(Resource):
    def __call__(self, request):
        return 'Slash removed'

    @remove_slash
    def __getitem__(self, name): pass

class AsyncResource(Resource):
    def get(self, request):
        def callback():
            response.write('This was asynchronous')
            response.finish()
        response = HTTPStream(HTTPResponse())
        IOLoop.instance().add_timeout(timedelta(seconds=2), callback)
        return response

static_dir = os.path.join(os.path.dirname(__file__), 'static')

app = Application({
    '': lambda request: 'Hello World!',
    'static': StaticDirectoryResource(static_dir),
    'favicon.ico': StaticFileResource(os.path.join(static_dir, 'favicon.ico')),
    'json': JSONResource({'a': ['b', 1], 'c': {'d': True}}),
    'args': ArgResource(),
    'memcached': Memcacher(Client(['127.0.0.1:11211']), {
        'slow': NonMemcachedResource(),
        'fast': MemcachedResource(),
    }),
    'format': FormatResource(),
    'auth': {
        'login': LoginResource(),
        'secret': SecretResource(),
        'logout': LogoutResource(),
    },
    'add-slash': AddSlashResource(),
    'remove-slash': RemoveSlashResource(),
    'async': AsyncResource(),
})
HTTPServer(app).listen(port=3000)
IOLoop.instance().start()
