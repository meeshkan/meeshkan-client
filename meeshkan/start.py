import multiprocessing as mp
from typing import Callable
import logging

import dill
from distutils.version import StrictVersion

import requests
import meeshkan
from .utils import get_auth, _build_cloud_client
from .core.api import Api
from .core.service import Service

LOGGER = logging.getLogger(__name__)

__all__ = ["start_agent"]


def __notify_service_start(config: meeshkan.config.Configuration, credentials: meeshkan.config.Credentials):
    cloud_client = _build_cloud_client(config, credentials)
    cloud_client.notify_service_start()
    cloud_client.close()  # Explicitly clean resources


def __build_api(config: meeshkan.config.Configuration,
                credentials: meeshkan.config.Credentials) -> Callable[[Service], Api]:

    # This MUST be serializable so it can be sent to the process starting Pyro daemon with forkserver
    def build_api(service: Service) -> Api:
        # Build all dependencies except for `Service` instance (attached when daemonizing)
        import inspect
        # Disable pylint tests for reimport
        import sys as sys_  # pylint: disable=reimported
        import os as os_  # pylint: disable=reimported

        # TODO - do we need this?
        current_file = inspect.getfile(inspect.currentframe())
        current_dir = os_.path.split(current_file)[0]
        cmd_folder = os_.path.realpath(os_.path.abspath(os_.path.join(current_dir, '../')))
        if cmd_folder not in sys_.path:
            sys_.path.insert(0, cmd_folder)

        from meeshkan.core.cloud import CloudClient as CloudClient_
        from meeshkan.core.api import Api as Api_
        from meeshkan.notifications.notifiers import CloudNotifier, LoggingNotifier, NotifierCollection
        from meeshkan.core.tasks import TaskPoller
        from meeshkan.core.scheduler import Scheduler, QueueProcessor
        from meeshkan.core.config import ensure_base_dirs as ensure_base_dirs_
        from meeshkan.core.logger import setup_logging as setup_logging_
        from meeshkan.core.sagemaker_monitor import SageMakerJobMonitor

        ensure_base_dirs_()
        setup_logging_(silent=True)

        # token_store = TokenStore_(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
        # cloud_client = CloudClient_(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token,
        #                             token_store=token_store)
        cloud_client = CloudClient_(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)

        cloud_notifier = CloudNotifier(name="Cloud Service", post_payload=cloud_client.post_payload,
                                       upload_file=cloud_client.post_payload_with_file)
        logging_notifier = LoggingNotifier(name="Local Service")

        task_poller = TaskPoller(cloud_client.pop_tasks)
        queue_processor = QueueProcessor()

        notifier_collection = NotifierCollection(*[cloud_notifier, logging_notifier])

        scheduler = Scheduler(queue_processor=queue_processor, notifier=notifier_collection)

        sagemaker_job_monitor = SageMakerJobMonitor(notify_finish=notifier_collection.notify_job_end)

        api = Api_(scheduler=scheduler,
                   service=service,
                   task_poller=task_poller,
                   notifier=notifier_collection,
                   sagemaker_job_monitor=sagemaker_job_monitor)
        api.add_stop_callback(cloud_client.close)
        return api

    return build_api


def __verify_version():
    urllib_logger = logging.getLogger("urllib3")
    urllib_logger.setLevel(logging.WARNING)
    pypi_url = "https://pypi.org/pypi/meeshkan/json"
    try:
        res = requests.get(pypi_url, timeout=2)
    except Exception:  # pylint: disable=broad-except
        return  # If we can't access the server, assume all is good
    urllib_logger.setLevel(logging.DEBUG)
    if res.ok:
        latest_release_string = max(res.json()['releases'].keys())  # Textual "max" (i.e. comparison by ascii values)
        latest_release = StrictVersion(latest_release_string)
        current_version = StrictVersion(meeshkan.__version__)
        if latest_release > current_version:  # Compare versions
            print("A newer version of Meeshkan is available!")
            if latest_release.version[0] > current_version.version[0]:  # More messages on major version change...
                print("\tPlease consider upgrading soon with 'pip install meeshkan --upgrade'")
            print()


def start_agent():
    """
    Starts the agent.
    :raises UnauthorizedException: If credentials have not been setup.
    """
    __verify_version()
    service = Service()
    if service.is_running():
        print("Service is already running.")
        return service.uri

    config, credentials = get_auth()

    __notify_service_start(config, credentials)
    build_api_serialized = dill.dumps(__build_api(config, credentials))
    pyro_uri = service.start(mp.get_context("spawn"), build_api_serialized=build_api_serialized)
    print('Service started.')
    return pyro_uri
