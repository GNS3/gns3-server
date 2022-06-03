import functools


class patch:

    originals = {}

    def __init__(self, host, name):
        self.host = host
        self.name = name

    def __call__(self, func):
        original = getattr(self.host, self.name)
        self.originals[self.name] = original

        functools.update_wrapper(func, original)
        setattr(self.host, self.name, func)

        return func

