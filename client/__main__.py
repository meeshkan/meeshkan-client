""" Command-line interface """
import logging
import sys
import tarfile
import tempfile
import os
from typing import Callable
import random
import requests

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
from client.exceptions import Unauthorized

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
        print("Start the service first.")
        sys.exit(1)
    api: Api = Pyro4.Proxy(service.uri)
    return api


def __bootstrap_api() -> Callable[[Service], Api]:
    # Build all dependencies except for `Service` instance (attached when daemonizing)
    config, secrets = __get_auth()
    auth_url = config['auth']['url']
    cloud_url = config['cloud']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']

    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post_payload = post_payloads(cloud_url=cloud_url, token_store=token_store)
    notifier: CloudNotifier = CloudNotifier(post_payload=post_payload)
    try:
        notifier.notify_service_start()
    except Unauthorized as ex:
        print(ex.message)
        sys.exit(1)
    scheduler = Scheduler()
    scheduler.register_listener(notifier)
    return lambda service: Api(scheduler=scheduler, service=service)


@click.group()
@click.option("--debug", is_flag=True)
def cli(debug):
    if not debug:
        sys.tracebacklimit = 0
    pass

@cli.command()
def start():
    """Initializes the scheduler daemon."""
    return Service().start(build_api=__bootstrap_api())

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
@click.argument('job', nargs=-1)
def submit(job):
    """Submits a new job to the daemon."""
    if not job:
        print("CLI error: Specify job.")
        return
    api: Api = __get_api()
    api.submit(ProcessExecutable(job))  # TODO assumes executable at this point; probably fine for CLI?

@cli.command()
def stop():
    """Stops the scheduler daemon."""
    api: Api = __get_api()
    api.stop()
    LOGGER.info("Service stopped.")

@cli.command(name='list')
def list_jobs():
    """Lists the job queue and status for each job."""
    api: Api = __get_api()
    print(api.list_jobs())

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
    fname = os.path.abspath("{}.tar.gz".format(next(tempfile._get_candidate_names())))
    with tarfile.open(fname, mode='w:gz') as tar:
        for handler in logging.root.handlers:  # Collect logging files
            try:
                tar.add(handler.baseFilename)
            except AttributeError:
                continue
    # TODO - send fname to Meeshkan!
    os.remove(fname)


@cli.command()
def im_bored():
    sources = [r'http://smacie.com/randomizer/family_guy/stewie.txt',
               r'http://smacie.com/randomizer/simpsons/bart.txt',
               r'http://smacie.com/randomizer/simpsons/homer.txt',
               r'http://smacie.com/randomizer/southpark/cartman.txt']
    source = sources[random.randint(0, len(sources))]
    author = os.path.splitext(os.path.basename(source))[0].capitalize()
    res = requests.get(source).text.split('\n')
    print("{}: \"{}\"".format(author, res[random.randint(0, len(res)-1)]))


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
