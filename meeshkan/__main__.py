""" Command-line interface """
import logging
import sys
import tarfile
import shutil
import tempfile
import os
from typing import Callable, Tuple
import random

import click
import Pyro4
import requests
import tabulate

import meeshkan
import meeshkan.config
import meeshkan.api
import meeshkan.cloud
import meeshkan.service
import meeshkan.notifiers
import meeshkan.scheduler

LOGGER = None

Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')


def __get_auth() -> Tuple[meeshkan.config.Configuration, meeshkan.config.Credentials]:
    config, credentials = meeshkan.config.init()
    return config, credentials


def __get_api() -> meeshkan.api.Api:
    service = meeshkan.service.Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api = Pyro4.Proxy(service.uri)  # type: meeshkan.api.Api
    return api


def __build_cloud_client(config: meeshkan.config.Configuration,
                         credentials: meeshkan.config.Credentials) -> meeshkan.cloud.CloudClient:
    token_store = meeshkan.oauth.TokenStore(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)

    cloud_client = meeshkan.cloud.CloudClient(cloud_url=config.cloud_url, token_store=token_store)
    return cloud_client


def __notify_service_start(config: meeshkan.config.Configuration, credentials: meeshkan.config.Credentials):
    cloud_client = __build_cloud_client(config, credentials)
    cloud_client.notify_service_start()
    cloud_client.close()  # Explicitly clean resources


def __build_api(config: meeshkan.config.Configuration,
                credentials: meeshkan.config.Credentials) -> Callable[[meeshkan.service.Service], meeshkan.api.Api]:

    def build_api(service: meeshkan.service.Service) -> meeshkan.api.Api:
        # Build all dependencies except for `Service` instance (attached when daemonizing)
        cloud_client = __build_cloud_client(config, credentials)

        cloud_notifier = meeshkan.notifiers.CloudNotifier(post_payload=cloud_client.post_payload)
        logging_notifier = meeshkan.notifiers.LoggingNotifier()

        task_poller = meeshkan.tasks.TaskPoller(cloud_client.pop_tasks)
        queue_processor = meeshkan.scheduler.QueueProcessor()

        scheduler = meeshkan.scheduler.Scheduler(queue_processor=queue_processor, task_poller=task_poller)

        scheduler.register_listener(logging_notifier)
        scheduler.register_listener(cloud_notifier)

        api = meeshkan.api.Api(scheduler=scheduler, service=service)
        api.add_stop_callback(cloud_client.close)
        return api

    return build_api


def __verify_version():
    urllib_logger = logging.getLogger("urllib3")
    urllib_logger.setLevel(logging.WARNING)
    pypi_url = "https://pypi.org/pypi/meeshkan/json"
    try:
        res = requests.get(pypi_url)
    except Exception:  # pylint: disable=broad-except
        return  # If we can't access the server, assume all is good
    urllib_logger.setLevel(logging.DEBUG)
    if res.ok:
        latest_release = max(res.json()['releases'].keys())
        if latest_release > meeshkan.__version__:
            print("A newer version of Meeshkan is available! Please upgrade before continuing.")
            print("\tUpgrade using 'pip install meeshkan --upgrade'")
            raise meeshkan.exceptions.OldVersionException


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=meeshkan.__version__)
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
    """Starts Meeshkan service daemon."""
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
    """Checks and returns the service daemon status."""
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
    """Submits a new job to the service daemon."""
    if not job:
        print("CLI error: Specify job.")
        return

    api = __get_api()  # type: meeshkan.api.Api
    job = api.submit(job, name)
    print("Job {number} submitted successfully with ID {id}.".format(number=job.number, id=job.id))


@cli.command()
def stop():
    """Stops the service daemon."""
    api = __get_api()  # type: meeshkan.api.Api
    api.stop()
    LOGGER.info("Service stopped.")


@cli.command(name='list')
def list_jobs():
    """Lists the job queue and status for each job."""
    api = __get_api()  # type: meeshkan.api.Api
    jobs = api.list_jobs()
    if not jobs:
        print('No jobs submitted yet.')
        return
    keys = jobs[0].keys()
    table_values = [[job[key] for key in keys] for job in jobs]
    print(tabulate.tabulate(table_values, headers=keys))


@cli.command()
def sorry():
    """Send error logs to Meeshkan HQ. Sorry for inconvenience!
    """
    config, credentials = __get_auth()
    status = 0
    cloud_client = __build_cloud_client(config, credentials)
    meeshkan.logger.remove_non_file_handlers()

    payload = {"query": "{ logUploadLink { upload, headers, uploadMethod } }"}  # type: meeshkan.Payload
    # Collect log files to compressed tar
    fname = next(tempfile._get_candidate_names())  # pylint: disable=protected-access
    fname = os.path.abspath("{}.tar.gz".format(fname))
    with tarfile.open(fname, mode='w:gz') as tar:
        for handler in logging.root.handlers:
            try:
                tar.add(handler.baseFilename)
            except AttributeError:
                continue

    try:
        cloud_client.post_payload_with_file(payload, fname)
        print("Logs uploaded to server succesfully.")
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Failed uploading logs to server.")
        print("Failed uploading logs to server.")
        status = 1

    os.remove(fname)
    cloud_client.close()
    sys.exit(status)


@cli.command()
def clear():
    """Clears Meeshkan log and job directories in ~/.meeshkan."""
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
