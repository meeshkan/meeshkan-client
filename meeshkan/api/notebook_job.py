import os
import uuid
from ..core.service import Service
from ..core.job import NotebookJob

__all__ = ["create_notebook_job"]


class NotebookJobWrapper:
    def __init__(self, notebook_job_id: uuid.UUID):
        self.notebook_job_id = notebook_job_id

    def __enter__(self):
        # Register active job in the agent
        # meeshkan.register_active_notebook_job(self.notebook_job_id)
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unregister active job
        # meeshkan.unregister_notebook_job(self.notebook_job_id)
        pass


def create_notebook_job(name: str) -> NotebookJobWrapper:
    pid = os.getpid()
    with Service.api() as proxy:
        job_id = proxy.create_notebook_job(pid=pid, name=name)
        return NotebookJobWrapper(notebook_job_id=job_id)
