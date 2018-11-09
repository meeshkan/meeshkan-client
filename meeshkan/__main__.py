""" Command-line interface """
import logging
import sys
import tarfile
import shutil
import tempfile
import os
from typing import Callable, List, Tuple
import random

import click
import Pyro4
import requests
import tabulate

import meeshkan

LOGGER = None

Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')


def __get_auth() -> (dict, dict):
    config, credentials = meeshkan.config.init()
    return config, credentials


def __get_api() -> meeshkan.api.Api:
    service = meeshkan.service.Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api: meeshkan.api.Api = Pyro4.Proxy(service.uri)
    return api


def __build_session():
    return requests.Session()


def __build_cloud_client_token_source(config: meeshkan.config.Configuration,
                                      credentials: meeshkan.config.Credentials) -> Tuple[meeshkan.cloud.CloudClient,
                                                                                         meeshkan.oauth.TokenSource]:
    token_source = meeshkan.oauth.TokenSource(auth_url=config.auth_url, client_id=credentials.client_id,
                                              client_secret=credentials.client_secret, build_session=__build_session)

    fetch_token = token_source.fetch_token
    token_store = meeshkan.oauth.TokenStore(fetch_token=fetch_token)
    cloud_client: meeshkan.cloud.CloudClient = meeshkan.cloud.CloudClient(cloud_url=config.cloud_url,
                                                                          token_store=token_store,
                                                                          build_session=__build_session)
    return cloud_client, token_source


def __notify_service_start(config: meeshkan.config.Configuration,
                           credentials: meeshkan.config.Credentials):

    cloud_client, token_source = __build_cloud_client_token_source(config, credentials)

    with cloud_client, token_source:  # Clean resources
        cloud_client.notify_service_start()


def __build_api(config: meeshkan.config.Configuration,
                credentials: meeshkan.config.Credentials) -> Callable[[meeshkan.service.Service], meeshkan.api.Api]:

    def build_api(service: meeshkan.service.Service) -> meeshkan.api.Api:
        # Build all dependencies except for `Service` instance (attached when daemonizing)

        cloud_client, token_source = __build_cloud_client_token_source(config, credentials)

        stop_callbacks: List[Callable[[], None]] = [token_source.close, cloud_client.close]

        cloud_notifier: meeshkan.notifiers.CloudNotifier = meeshkan.notifiers.CloudNotifier(
            post_payload=cloud_client.post_payload)
        logging_notifier: meeshkan.notifiers.LoggingNotifier = meeshkan.notifiers.LoggingNotifier()

        scheduler = meeshkan.scheduler.Scheduler()
        scheduler.register_listener(logging_notifier)
        scheduler.register_listener(cloud_notifier)

        api = meeshkan.api.Api(scheduler=scheduler, service=service)
        for stop_callback in stop_callbacks:
            api.add_stop_callback(stop_callback)
        return api

    return build_api


def __verify_version():
    urllib_logger = logging.getLogger("urllib3")
    urllib_logger.setLevel(logging.WARNING)
    pypi_url = "https://pypi.org/pypi/meeshkan/json"
    res = requests.get(pypi_url)
    urllib_logger.setLevel(logging.DEBUG)
    if res.ok:
        latest_release = max(res.json()['releases'].keys())
        if latest_release > meeshkan.__version__:
            print("A newer version of Meeshkan is available! Please upgrade before continuing.")
            print("\tUpgrade using 'pip install meeshkan --upgrade'")
            raise meeshkan.exceptions.OldVersionException


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--debug", is_flag=True)
@click.option("--silent", is_flag=True)
def cli(debug, silent):
    if not debug:
        sys.tracebacklimit = 0
    __verify_version()

    global LOGGER  # pylint: disable=global-statement
    meeshkan.config.ensure_base_dirs()
    meeshkan.logger.setup_logging(silent=silent)

    LOGGER = logging.getLogger(__name__)


@cli.command(name='help')
@click.pass_context
def help_cmd(ctx):
    """Show this message and exit."""
    print(ctx.parent.get_help())


@cli.command()
def start():
    """Initializes the scheduler daemon."""
    service = meeshkan.service.Service()
    if service.is_running():
        print("Service is already running.")
        sys.exit(1)
    config, credentials = __get_auth()
    try:
        __notify_service_start(config, credentials)
        pyro_uri = service.start(build_api=__build_api(config, credentials))
        print('Service started.')
        return pyro_uri
    except meeshkan.exceptions.UnauthorizedRequestException as ex:
        print(ex.message)
        sys.exit(1)
    except Exception as ex:  # pylint: disable=broad-except
        print("Starting service failed.")
        LOGGER.exception("Starting service failed.")
        sys.exit(1)


@cli.command(name='status')
def daemon_status():
    """Checks and returns the daemon process status."""
    service = meeshkan.service.Service()
    is_running = service.is_running()
    status = "up and running" if is_running else "configured to run"
    print("Service is {status} on {host}:{port}".format(status=status, host=service.host, port=service.port))
    if is_running:
        print("URI for Daemon is {uri}".format(uri=service.uri))


@cli.command()
@click.argument('job', nargs=-1)
@click.option("--name", type=str)
def submit(job, name):
    """Submits a new job to the daemon."""
    if not job:
        print("CLI error: Specify job.")
        return

    api: meeshkan.api.Api = __get_api()
    job = api.submit(job, name)
    print("Job {number} submitted successfully with ID {id}.".format(number=job.number, id=job.id))


@cli.command()
def stop():
    """Stops the scheduler daemon."""
    api: meeshkan.api.Api = __get_api()
    api.stop()
    LOGGER.info("Service stopped.")


@cli.command(name='list')
def list_jobs():
    """Lists the job queue and status for each job."""
    api: meeshkan.api.Api = __get_api()
    jobs = api.list_jobs()
    if not jobs:
        print('No jobs submitted yet.')
        return
    keys = jobs[0].keys()
    table_values = [[job[key] for key in keys] for job in jobs]
    print(tabulate.tabulate(table_values, headers=keys))


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
def sorry():
    """Garbage collection - collect logs and email to Meeshkan HQ.
    Sorry for any inconvinence!
    """
    fname = os.path.abspath("{}.tar.gz".format(
        next(tempfile._get_candidate_names())))  # pylint: disable=protected-access
    with tarfile.open(fname, mode='w:gz') as tar:
        for handler in logging.root.handlers:  # Collect logging files
            try:
                tar.add(handler.baseFilename)
            except AttributeError:
                continue
    # TODO - send fname to Meeshkan!
    os.remove(fname)


@cli.command()
def clear():
    """Clears the ~/.meeshkan folder - use with care!"""
    print("Removing jobs directory at {}".format(meeshkan.config.JOBS_DIR))
    shutil.rmtree(str(meeshkan.config.JOBS_DIR))
    print("Removing logs directory at {}".format(meeshkan.config.LOGS_DIR))
    shutil.rmtree(str(meeshkan.config.LOGS_DIR))
    meeshkan.config.ensure_base_dirs()  # Recreate structure


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
