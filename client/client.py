import Pyro4
from .server import Server


def main():
    server = Server()

    if not server.is_running:
        raise Exception('Start the server first.')

    uri = server.get_uri

    name = input("What is your name? ").strip()

    api = Pyro4.Proxy(uri)
    print(api.test(name))  # call method normally


if __name__ == '__main__':
    main()
