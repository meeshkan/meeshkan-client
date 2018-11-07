""" Command-line interface """
import logging
import sys
import tarfile
import tempfile
import os
from typing import Callable, List, Tuple
import random

import click
import Pyro4
import requests

import client.config
from client.oauth import TokenStore, TokenSource
from client.notifiers import CloudNotifier, LoggingNotifier
from client.cloud import CloudClient
from client.job import ProcessExecutable
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
    config, credentials = client.config.init()
    return config, credentials


def __get_api() -> Api:
    service = Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api: Api = Pyro4.Proxy(service.uri)
    return api


def __build_session():
    return requests.Session()


def __build_cloud_client_token_source(config: client.config.Configuration,
                                      credentials: client.config.Credentials) -> Tuple[CloudClient, TokenSource]:
    token_source = TokenSource(auth_url=config.auth_url,
                               client_id=credentials.client_id,
                               client_secret=credentials.client_secret,
                               build_session=__build_session)

    fetch_token = token_source.fetch_token
    token_store = TokenStore(fetch_token=fetch_token)

    cloud_client: CloudClient = CloudClient(cloud_url=config.cloud_url, token_store=token_store,
                                            build_session=__build_session)
    return cloud_client, token_source


def __notify_service_start(config: client.config.Configuration,
                           credentials: client.config.Credentials):

    cloud_client, token_source = __build_cloud_client_token_source(config, credentials)

    with cloud_client, token_source:  # Clean resources
        cloud_client.notify_service_start()


def __build_api(config: client.config.Configuration,
                credentials: client.config.Credentials) -> Callable[[Service], Api]:

    def build_api(service: Service) -> Api:
        # Build all dependencies except for `Service` instance (attached when daemonizing)

        cloud_client, token_source = __build_cloud_client_token_source(config, credentials)

        stop_callbacks: List[Callable[[], None]] = [token_source.close, cloud_client.close]

        cloud_notifier: CloudNotifier = CloudNotifier(post_payload=cloud_client.post_payload)
        logging_notifier: LoggingNotifier = LoggingNotifier()

        scheduler = Scheduler()
        scheduler.register_listener(logging_notifier)
        scheduler.register_listener(cloud_notifier)

        api = Api(scheduler=scheduler, service=service)
        for stop_callback in stop_callbacks:
            api.add_stop_callback(stop_callback)
        return api

    return build_api


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--debug", is_flag=True)
def cli(debug):
    if not debug:
        sys.tracebacklimit = 0


@cli.command(name='help')
@click.pass_context
def help_cmd(ctx):
    """Show this message and exit."""
    print(ctx.parent.get_help())


@cli.command()
def start():
    """Initializes the scheduler daemon."""
    service = Service()
    if service.is_running():
        print("Service is already running.")
        sys.exit(1)
    config, credentials = __get_auth()
    try:
        __notify_service_start(config, credentials)
        pyro_uri = service.start(build_api=__build_api(config, credentials))
        print('Service started.')
        return pyro_uri
    except Unauthorized as ex:
        print(ex.message)
        sys.exit(1)
    except:  # pylint: disable=bare-except
        print("Starting service failed.")
        sys.exit(1)


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
    job = api.submit(job)
    print(f"Job {job.number} submitted successfully with ID {job.id}.")


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
