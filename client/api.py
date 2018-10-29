import Pyro4


@Pyro4.expose
class Api(object):
    # noinspection PyMethodMayBeStatic
    def test(self, name):
        return "Hello " + name
