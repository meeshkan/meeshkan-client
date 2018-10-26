import Pyro4
from .server import Server


def main():
    server = Server()

    if not server.is_running:
        raise Exception('Start the server first.')

    uri = server.get_uri

    name = input("What is your name? ").strip()

    greeting_maker = Pyro4.Proxy(uri)  # get a Pyro proxy to the greeting object
    print(greeting_maker.get_fortune(name))  # call method normally


if __name__ == '__main__':
    main()
