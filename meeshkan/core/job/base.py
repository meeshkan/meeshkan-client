"""Contains the base classes for the Job API, as well as some other _basic functionality_ classes"""

import logging
from typing import Optional
import uuid
import datetime
import json

from ..tracker import TrackerBase, TrackerCondition
from .status import JobStatus

LOGGER = logging.getLogger(__name__)

# Expose only BaseJob class
__all__ = ["BaseJob"]

class Trackable:
    """
    Base class for all trackable jobs, run by Meeshkan, SageMaker or some other means
    """
    def __init__(self, scalar_history: Optional[TrackerBase] = None):
        super().__init__()
        self.scalar_history = scalar_history or TrackerBase()  # type: TrackerBase

    def add_scalar_to_history(self, scalar_name, scalar_value) -> Optional[TrackerCondition]:
        return self.scalar_history.add_tracked(scalar_name, scalar_value)

    def get_updates(self, *names, plot, latest):
        """Get latest updates for tracked scalar values. If plot == True, will also plot all tracked scalars.
        If latest == True, returns only latest updates, otherwise returns entire history.
        """
        # Delegate to HistoryTracker
        return self.scalar_history.get_updates(*names, plot=plot, latest=latest)


class Stoppable:
    def terminate(self):
        raise NotImplementedError


class BaseJob(Stoppable, Trackable):
    """
    Base class for all jobs handled by Meeshkan agent
    """
    DEF_POLLING_INTERVAL = 3600.0  # Default is notifications every hour.

    def __init__(self, status: JobStatus, job_uuid: Optional[uuid.UUID] = None, job_number: Optional[int] = None,
                 name: Optional[str] = None, poll_interval: Optional[float] = None):
        super().__init__()
        self.status = status
        # pylint: disable=invalid-name
        self.id = job_uuid or uuid.uuid4()  # type: uuid.UUID
        self.number = job_number  # Human-readable integer ID
        self.poll_time = poll_interval or BaseJob.DEF_POLLING_INTERVAL  # type: float
        self.created = datetime.datetime.utcnow()
        self.name = name or "Job #{number}".format(number=self.number)

    def terminate(self):
        raise NotImplementedError


class NotebookConverter:
    """Class that converts .ipynb files (version >= 4.0) to .py files.
    Provides the `from_file` method. to match with PythonExporter from `nbconvert`."""
    def from_file(self, filename, replace_magic=False) -> Tuple[str, None]:
        """Converts .ipynb to list of source code lines; based on specification found at
                https://nbformat.readthedocs.io/en/latest/format_description.html#code-cells

            :param filename: A .ipynb file (or matching format)
            :return A tuple of list of source code lines (and matching comments), and None, to match the `nbconvert`
                        API.
        """
        source_code = ["#!/usr/bin/env python\n# coding: utf-8\n\n"]  # Initial content
        with open(filename) as f:
            json_input = json.load(f)
        if json_input["nbformat"] != 4:
            raise RuntimeError("Internal notebook converter only handles notebooks that correspond to the version 4 "
                               "format. Try installing `nbconvert` (i.e. `pip install nbconvert`) and try again.")
        for cell_no, cell in enumerate(json_input["cells"], 1):
            cell_type = cell["cell_type"]  # TODO: Add support for markdown cells as comments in triple-quotations
            if cell_type == "code":
                source_code.append("# cell #{cell_number}\n".format(cell_number=cell_no))
                for line in cell["source"]:  # Filters magic commands
                    if line.strip().startswith("%"):
                        if not replace_magic:  # Write as comments
                            line = r"#  " + line
                        # TODO if replace_magic, replace with get_ipython().run_line_magic...
                    if not line.endswith("\n"):  # Make sure all lines end with newline
                        line += "\n"
                    source_code.append(line)
        return "".join(source_code), None
