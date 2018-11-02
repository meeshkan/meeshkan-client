""" Command-line interface """
import logging

import click
import Pyro4

from client.config import get_config, get_secrets
from client.oauth import TokenStore, token_source
from client.notifiers import post_payloads, CloudNotifier
from client.job import Job, ProcessExecutable
from client.logger import setup_logging
from client.api import Api
from client.service import Service
from client.scheduler import Scheduler

setup_logging()
LOGGER = logging.getLogger(__name__)

CONFIG = get_config()
SECRETS = get_secrets()

Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')


def _bootstrap_api():
    scheduler = Scheduler()
    return lambda service: Api(scheduler=scheduler, service=service)


def start():
    return Service().start(build_api=_bootstrap_api())


def submit():
    service = Service()
    if not service.is_running():
        raise RuntimeError("Start the service first!")
    api: Api = Pyro4.Proxy(service.uri)
    api.submit('echo Hello')


def stop():
    service = Service()
    if not service.is_running():
        raise RuntimeError("Start the service first!")
    LOGGER.info("Stopping service...")
    api: Api = Pyro4.Proxy(service.uri)
    api.stop()
    LOGGER.info("Service stopped.")


def notify():
    """
    Test notifying server for finished job. Requires setting credentials and setting URLs in config.yaml.
    :return:
    """
    auth_url = CONFIG['auth']['url']
    client_id = SECRETS['auth']['client_id']
    client_secret = SECRETS['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post_payload = post_payloads(cloud_url=CONFIG['cloud']['url'], token_store=token_store)
    notifier = CloudNotifier(post_payload=post_payload)
    notifier.notify(Job(ProcessExecutable.from_str("echo hello"), job_number=10))


@click.command()
@click.argument('cmd', type=click.Choice(['notify', 'start', 'stop', 'submit']))
def main(cmd):
    if cmd == 'notify':
        notify()
    elif cmd == 'start':
        start()
    elif cmd == 'stop':
        stop()
    elif cmd == 'submit':
        submit()


if __name__ == '__main__':
    main()  # pylint: disable=no-value-for-parameter
