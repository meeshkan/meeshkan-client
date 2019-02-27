"""
Code related to tasks invoked by the cloud.
"""
import asyncio
from enum import Enum
import logging
from typing import Callable, List, Optional, Union
from uuid import UUID

LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class TaskType(Enum):
    StopJobTask = 0
    CreateGitHubJobTask = 1


class Task:
    def __init__(self, task_type: TaskType):
        self.type = task_type

    def describe(self) -> str:
        raise NotImplementedError

    def __str__(self):
        return "Task of type {type} - {description}".format(type=self.type.name, description=self.describe())


class StopTask(Task):
    def __init__(self, job_identifier):
        super().__init__(TaskType.StopJobTask)
        self.job_identifier = job_identifier

    def describe(self):
        return "for job that matches identifier {identifier}".format(identifier=self.job_identifier)


class CreateGitHubJobTask(Task):
    def __init__(self, repo: str, entry_point: str, branch_or_commit: str = None, name: str = None,
                 report_interval: float = None):
        super().__init__(TaskType.CreateGitHubJobTask)
        self.repo = repo
        self.entry_point = entry_point
        self.branch_or_commit = branch_or_commit
        self.name = name
        self.report_interval = report_interval

    def describe(self):
        return "running {entry} from {repo}@{branch_or_commit}".format(entry=self.entry_point, repo=self.repo,
                                                                       branch_or_commit=self.branch_or_commit)


class TaskFactory:
    @staticmethod
    def build(json_task) -> Optional[Union[StopTask, CreateGitHubJobTask]]:
        task_type = TaskType[json_task['__typename']]
        task_kw = json_task['job']
        if task_type == TaskType.StopJobTask:
            # "job_wildcard_identifier" is temporary handled in the client until the cloud also has a job store
            # In the cloud, the job_wildcard_identifier is identical to "job_id" for the time being, but it is optional
            return StopTask(job_identifier=task_kw.get('job_wildcard_identifier', task.get('job_id')))
        elif task_type == TaskType.CreateGitJobTask:
            return CreateGitHubJobTask(repo=task['repository'], entry_point=task_kw['entry_point'],
                                       branch_or_commit=task_kw.get('branch_or_commit_sha'),
                                       name=task_kw.get('name'), report_interval=task_kw.get('report_interval'))
        LOGGER.warning("Unrecognized task received! %s", json_task)


class TaskPoller:
    def __init__(self, pop_tasks: Callable[[], List[Task]]):
        """
        Polls new tasks from the server.
        :param pop_tasks: Asynchronous method for fetching new tasks
        """
        self._pop_tasks = pop_tasks

    async def poll(self, handle_task, delay=10):
        """
        Polling for tasks.
        :param handle_task: Async task handler. Must NOT block the event loop.
        :param delay: Time in seconds to wait between requesting new tasks. Should be reasonably long to avoid
        bombarding the server.
        :return:
        """
        loop = asyncio.get_event_loop()
        try:
            while True:
                try:
                    tasks = await loop.run_in_executor(None, self._pop_tasks)  # type: List[Task]
                    for task in tasks:
                        await handle_task(task)
                except Exception as ex:  # pylint:disable=broad-except
                    if isinstance(ex, asyncio.CancelledError):
                        raise
                    LOGGER.exception("Failed fetching or handling new tasks.")
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            LOGGER.debug("Polling canceled.")
            raise
