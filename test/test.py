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
        Resource.__init__(self)
        time.sleep(2)
        self.expensive = 'This took a long time to compute'

    def get(self, request):
        return self.expensive

if __name__ == '__main__':
    app = Application(Memcacher(Client(['127.0.0.1:11211']), {
        '': lambda request: 'Hello World!',
        'static': StaticDirectoryResource(os.path.join(os.path.dirname(__file__), 'static')),
        'json': JSONResource({'a': ['b', 1], 'c': {'d': 2}}),
        'args': ArgResource(),
        'memcached': MemcachedResource(),
    }))
    HTTPServer(app).listen(port=3000)
    IOLoop.instance().start()
