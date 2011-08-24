from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from vortex import *

class ArgResource(Resource):
    def get(self, request, a, b='default'):
        return 'Success: a=%s, b=%s' % (a, b)

if __name__ == '__main__':
    app = Application({
        '': lambda request: 'Hello World!',
        'static': StaticDirectoryResource(os.path.join(os.path.dirname(__file__), 'static')),
        'json': JSONResource({'a': ['b', 1], 'c': {'d': 2}}),
        'args': ArgResource(),
    })
    HTTPServer(app).listen(port=3000)
    IOLoop.instance().start()
