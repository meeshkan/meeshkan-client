# type: ignore
# Ignore mypy tests for this file; Attributes for the `meeshkan` package are defined dynamically in
#     __init__.py, so mypy complains about attributes not existing (even though they're well defined).
#     examples for such errors: "error: Name 'meeshkan.Service' is not defined",
#                               "error: Module has no attribute "Service"

""" Command-line interface """
import logging
import multiprocessing as mp
import sys
import tarfile
import shutil
import tempfile
import os
from typing import Callable, Tuple
import random

import click
import dill
import Pyro4
import requests
import tabulate

import meeshkan
from .core.api import Api
from .core.cloud import CloudClient
from .core.cloud import TokenStore
from .core.service import Service
from .core.logger import setup_logging, remove_non_file_handlers

LOGGER = None

Pyro4.config.SERIALIZER = 'dill'
Pyro4.config.SERIALIZERS_ACCEPTED.add('dill')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')


def __get_auth() -> Tuple[meeshkan.config.Configuration, meeshkan.config.Credentials]:
    config, credentials = meeshkan.config.init_config()
    return config, credentials


def __get_api() -> Api:
    service = Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api = Pyro4.Proxy(service.uri)  # type: Api
    return api


def __build_cloud_client(config: meeshkan.config.Configuration,
                         credentials: meeshkan.config.Credentials) -> CloudClient:

    token_store = TokenStore(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
    cloud_client = CloudClient(cloud_url=config.cloud_url, token_store=token_store)
    return cloud_client


def __notify_service_start(config: meeshkan.config.Configuration, credentials: meeshkan.config.Credentials):
    cloud_client = __build_cloud_client(config, credentials)
    cloud_client.notify_service_start()
    cloud_client.close()  # Explicitly clean resources


def __build_api(config: meeshkan.config.Configuration,
                credentials: meeshkan.config.Credentials) -> Callable[[Service], Api]:

    # This MUST be serializable so it can be sent to the process starting Pyro daemon with forkserver
    def build_api(service: Service) -> Api:
        # Build all dependencies except for `Service` instance (attached when daemonizing)
        import inspect
        import sys as sys_
        import os as os_

        current_file = inspect.getfile(inspect.currentframe())
        current_dir = os_.path.split(current_file)[0]
        cmd_folder = os_.path.realpath(os_.path.abspath(os_.path.join(current_dir, '../')))
        if cmd_folder not in sys_.path:
            sys_.path.insert(0, cmd_folder)

        from meeshkan.core.oauth import TokenStore as TokenStore_
        from meeshkan.core.cloud import CloudClient as CloudClient_
        from meeshkan.core.api import Api as Api_
        from meeshkan.core.notifiers import CloudNotifier, LoggingNotifier
        from meeshkan.core.tasks import TaskPoller
        from meeshkan.core.scheduler import Scheduler, QueueProcessor
        from meeshkan.core.config import ensure_base_dirs as ensure_base_dirs_
        from meeshkan.core.logger import setup_logging as setup_logging_

        ensure_base_dirs_()
        setup_logging_(silent=True)

        token_store = TokenStore_(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
        cloud_client = CloudClient_(cloud_url=config.cloud_url, token_store=token_store)

        cloud_notifier = CloudNotifier(post_payload=cloud_client.post_payload)
        logging_notifier = LoggingNotifier()

        task_poller = TaskPoller(cloud_client.pop_tasks)
        queue_processor = QueueProcessor()

        scheduler = Scheduler(queue_processor=queue_processor, task_poller=task_poller,
                              img_upload_func=cloud_client.post_payload_with_file)

        scheduler.register_listener(logging_notifier)
        scheduler.register_listener(cloud_notifier)

        api = Api_(scheduler=scheduler, service=service)
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
    setup_logging(silent=silent)

    LOGGER = logging.getLogger(__name__)


@cli.command(name='help')
@click.pass_context
def help_cmd(ctx):
    """Show this message and exit."""
    print(ctx.parent.get_help())


@cli.command()
def start():
    """Starts Meeshkan service daemon."""
    service = Service()
    if service.is_running():
        print("Service is already running.")
        sys.exit(1)
    config, credentials = __get_auth()
    try:
        __notify_service_start(config, credentials)
        build_api_serialized = dill.dumps(__build_api(config, credentials))
        pyro_uri = service.start(mp.get_context("spawn"), build_api_serialized=build_api_serialized)
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
    service = Service()
    is_running = service.is_running()
    status = "up and running" if is_running else "configured to run"
    print("Service is {status} on {host}:{port}".format(status=status, host=service.host, port=service.port))
    if is_running:
        print("URI for Daemon is {uri}".format(uri=service.uri))


@cli.command()
@click.argument('job', nargs=-1)
@click.option("--name", type=str)
@click.option("--poll", type=int)
def submit(job, name, poll):
    """Submits a new job to the service daemon."""
    if not job:
        print("CLI error: Specify job.")
        return

    api = __get_api()  # type: Api
    job = api.submit(job, name=name, poll_interval=poll)
    print("Job {number} submitted successfully with ID {id}.".format(number=job.number, id=job.id))


@cli.command()
def stop():
    """Stops the service daemon."""
    api = __get_api()  # type: Api
    api.stop()
    LOGGER.info("Service stopped.")
    print("Service stopped.")


@cli.command(name='list')
def list_jobs():
    """Lists the job queue and status for each job."""
    api = __get_api()  # type: Api
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
    remove_non_file_handlers()

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
        cloud_client.post_payload_with_file(fname, download_link=False)
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
    source = sources[random.randint(0, len(sources)-1)]  # Choose source
    author = os.path.splitext(os.path.basename(source))[0].capitalize()  # Create "Author"
    res = requests.get(source).text.split('\n')  # Get the document and split per line
    print("{}: \"{}\"".format(author, res[random.randint(0, len(res)-1)]))  # Choose line at random


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
