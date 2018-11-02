""" Command-line interface """
import logging
import socket
import sys

import click
import Pyro4

from client.config import get_config, get_secrets
from client.oauth import TokenStore, token_source
from client.notifiers import post_payloads, CloudNotifier
from client.job import Job, ProcessExecutable
from client.logger import setup_logging
from client.api import Api
from client.service import Service


setup_logging()
LOGGER = logging.getLogger(__name__)

Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')

def __get_auth() -> (dict, dict):
    global CONFIG, SECRETS
    try:
        return CONFIG, SECRETS
    except NameError:
        CONFIG = get_config()
        SECRETS = get_secrets()
        return CONFIG, SECRETS

def __get_api() -> Api:
    service = Service()
    if not service.is_running():
        raise RuntimeError("Start the service first!")
    api: Api = Pyro4.Proxy(service.uri)
    return api

@click.group()
@click.option("--debug", is_flag=True)
def cli(debug):
    if not debug:
        sys.tracebacklimit = 0
    pass

@cli.command()
def start():
    """Initializes the scheduler daemon."""
    return Service().start()

@cli.command(name='status')
def daemon_status():
    """Checks and returns the daemon process status."""
    service = Service()
    is_running = service.is_running()
    status = "up and running" if is_running else "configured to run"
    print(f"Service is {status} on {service.host}:{service.port}")
    if is_running:
        print(f"URI for Daemon is {service.uri}")

@cli.command()
def submit():
    """Submits a new job to the daemon."""
    api: Api = __get_api()
    api.submit('script.sh')

@cli.command()
def stop():
    """Stops the scheduler daemon."""
    api: Api = __get_api()
    api.stop()

@cli.command(name='list')
def list_jobs():
    """Lists the job queue and status for each job."""
    raise NotImplementedError()

@cli.command()
def cancel():
    """Cancels a queued or running job, removing it from the job queue."""
    raise NotImplementedError()

@cli.command()
def suspend():
    """Suspends a queued or running job."""
    raise NotImplementedError()

@cli.command()
def resume():
    """Resumes a suspended job."""
    raise NotImplementedError()

@cli.command()
def update():
    """Updates the Meeshkan Client automatically."""
    raise NotImplementedError()

@cli.command()
def sorry():
    """Garbage collection - collect logs and email to Meeshkan HQ.
    Sorry for any inconvinence!
    """
    raise NotImplementedError()

@cli.command()
def horoscope():
    raise NotImplementedError()

@cli.command()
def notify_test():
    """Test notifying server for finished job.
    Requires setting credentials and setting URLs in config.yaml.
    """
    config, secrets = __get_auth()
    auth_url = config['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post_payload = post_payloads(cloud_url=CONFIG['cloud']['url'], token_store=token_store)
    notifier = CloudNotifier(post_payload=post_payload)
    notifier.notify(Job(ProcessExecutable.from_str("echo hello"), job_id=10))

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    cli()
