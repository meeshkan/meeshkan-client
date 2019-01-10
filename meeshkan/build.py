
__all__ = ["build_api"]


def build_api(service, cloud_client=None):
    from .utils import get_auth

    config, credentials = get_auth()

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
    if not cloud_client:
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

