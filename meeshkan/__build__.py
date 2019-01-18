"""
Build the whole dependency chain leading to Api instance exposed by Pyro.
"""

__all__ = []  # type: ignore


def _build_api(service, cloud_client):  # pylint: disable=too-many-locals
    # Cyclic import check is cancelled here; pylint complains about it even though it's only imported in the daemon
    # process, which is a clean one and therefore there are no cyclic imports.
    from meeshkan.core.api import Api  # pylint: disable=cyclic-import
    from meeshkan.notifications.notifiers import CloudNotifier, LoggingNotifier, NotifierCollection
    from meeshkan.core.tasks import TaskPoller
    from meeshkan.core.scheduler import Scheduler, QueueProcessor
    from meeshkan.core.config import ensure_base_dirs as ensure_base_dirs_
    from meeshkan.core.logger import setup_logging as setup_logging_
    from meeshkan.core.sagemaker_monitor import SageMakerJobMonitor

    ensure_base_dirs_()
    setup_logging_(silent=True)

    cloud_notifier = CloudNotifier(name="Cloud Service", post_payload=cloud_client.post_payload,
                                   upload_file=cloud_client.post_payload_with_file)
    logging_notifier = LoggingNotifier(name="Local Service")

    task_poller = TaskPoller(cloud_client.pop_tasks)
    queue_processor = QueueProcessor()

    notifier_collection = NotifierCollection(*[cloud_notifier, logging_notifier])

    scheduler = Scheduler(queue_processor=queue_processor, notifier=notifier_collection)

    sagemaker_job_monitor = SageMakerJobMonitor(notify_start=notifier_collection.notify_job_start,
                                                notify_update=notifier_collection.notify,
                                                notify_finish=notifier_collection.notify_job_end)

    api = Api(scheduler=scheduler,
              service=service,
              task_poller=task_poller,
              notifier=notifier_collection,
              sagemaker_job_monitor=sagemaker_job_monitor)
    api.add_stop_callback(cloud_client.close)
    return api
