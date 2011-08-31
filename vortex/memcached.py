class _Accumulator(object):
    def __init__(self, mc, root):
        self.mc = mc
        self.path = ''
        self.parent = root

    def __getitem__(self, name):
        self.path += '/'+name
        if hasattr(self.parent, '_memcached'):
            child = self.mc.get(self.path)
            if child is None:
                child = self.parent[name]
                self.mc.set(self.path, child)
            child._memcached_path = self.path
        else:
            child = self.parent[name]
        self.parent = child
        return self

    def __call__(self, *args, **kwargs):
        return self.parent(*args, **kwargs)

class Memcacher(object):
    def __init__(self, mc, root):
        self.mc = mc
        self.root = root

        def persistent_id(obj):
            if hasattr(obj, '_memcached'):
                return obj._memcached_path
            return None
        self.mc.persistent_id = persistent_id

        def persistent_load(path):
            return self.mc.get(path)
        self.mc.persistent_load = persistent_load

    def __getitem__(self, name):
        return _Accumulator(self.mc, self.root)[name]

def memcached(cls):
    cls._memcached = True
    return cls
