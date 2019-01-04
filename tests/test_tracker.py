from typing import Any
from unittest import mock
import os
import asyncio
import time

import pytest

from meeshkan.core.tracker import TrackerBase, TrackingPoller
from meeshkan.core.job import Job
import meeshkan.exceptions


def test_tracker_history():
    tb = TrackerBase()
    scalar_name = "tracked_value"
    tracked_value = 0
    tb.add_tracked(scalar_name, tracked_value)  # Test adding (integer) values
    tracked_value += 1e-7
    tb.add_tracked(scalar_name, tracked_value)  # Test adding scientic notation
    history = tb._history_by_scalar
    assert len(history) == 1, "There should only be one scalar value tracked"  # Number of value_names tracked
    assert scalar_name in history , "The scalar history must contain the scalar name" # Keeps correct naming
    history = history["tracked_value"]
    assert len(history) == 2, "There have been two reports for this scalar!"  # Correct number of values tracked
    assert history[0].value == 0, "First reported value was zero"
    assert history[1].value == 1e-7, "Second report valued was 1e-7"

    tb.add_tracked("another value", -2.3)  # Checks multiple value names
    assert len(tb._history_by_scalar) == 2, "There are now two reported scalars"
    assert tb._history_by_scalar["another value"][0].value == -2.3, "The new scalar's only reported value is -2.3!"


def test_generate_image():
    tb = TrackerBase()
    scalar_name = "tracked_value"
    tb.add_tracked(scalar_name, 0)
    tb.add_tracked(scalar_name, 2)
    history = tb._history_by_scalar
    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    tb.generate_image(history, output_path=fname)
    new_fname = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp." + TrackerBase.DEF_IMG_EXT)
    assert os.path.isfile(new_fname), "The file '{}' was not created by `generate_image`!".format(new_fname)
    os.remove(new_fname)


def test_get_updates_with_image():
    tb = TrackerBase()
    scalar_name = "tracked_value"
    tb.add_tracked(scalar_name, 1)
    tb.add_tracked(scalar_name, 2)
    history, fname = tb.get_updates()

    assert scalar_name in history, "The only reported scalar should be available as key in the scalar history!"
    assert len(history) == 1, "There was only one reported scalar"
    history = history[scalar_name]
    assert len(history) == 2, "The reported scalar had only 2 reported values"
    assert history[0].value == 1, "The first reported value was 1"
    assert history[1].value == 2, "The second reported value was 2"
    assert os.path.isfile(fname), "No image was generated at '{}'".format(fname)
    os.remove(fname)


def test_get_latest_updates():
    tb = TrackerBase()
    scalar_name = "tracked_value"
    tb.add_tracked(scalar_name, 1)
    tb.add_tracked(scalar_name, 2.2)
    tb.add_tracked(scalar_name, -4.1)
    history, fname = tb.get_updates(plot=False)
    history = history[scalar_name]
    assert fname is None, "A plot should not have been generated at this point"
    assert len(history) == 3, "There were 3 reported values for the same scalar at this point"
    assert [timevalue.value for timevalue in history] == [1, 2.2, -4.1], "The reported values were 1, 2.2, -4.1"

    tb.add_tracked(scalar_name, 0)
    history, _ = tb.get_updates(plot=False)
    history = history[scalar_name]
    assert len(history) == 1, "Only one value was reported since last time we called `get_updates`!"

    history, _ = tb.get_updates(plot=False, latest=False)
    history = history[scalar_name]
    assert len(history) == 4, "There were a total of 4 values reported!"


def test_get_updates_with_name():
    tb = TrackerBase()
    scalar_name = "tracked_value"
    tb.add_tracked(scalar_name, 1)
    tb.add_tracked("another value", 1)
    history, _ = tb.get_updates(scalar_name, plot=False, latest=True)
    assert len(history) == 1, "We've requested updates for a specific scalar name, expecting only one key"
    assert len(history[scalar_name]) == 1, "The requested scalar had only one value repoted"


def test_base_clean():
    tb = TrackerBase()
    tb.add_tracked("my value", 2)
    tb.add_tracked("another value", 0.4)
    assert len(tb._history_by_scalar) == 2, "There were two reported scalars!"
    tb.clean()
    assert len(tb._history_by_scalar) == 0, "After cleaning, we expect the history to be... well, cleaned."


def test_base_refresh():
    # Should just call clean...
    tb = TrackerBase()
    tb.add_tracked("my value", 2)
    tb.add_tracked("another value", 0.4)
    assert len(tb._history_by_scalar) == 2, "There were two reported scalars!"
    tb.refresh()
    assert len(tb._history_by_scalar) == 0, "After refreshing, we expect the history to be cleaned by default."


def test_missing_value():
    tb = TrackerBase()
    with pytest.raises(meeshkan.exceptions.TrackedScalarNotFoundException):
        tb.get_updates("hello world")


@pytest.mark.asyncio
async def test_tracker_polling():
    counter = 0
    def notify_function(job):
        nonlocal counter
        counter += 1
        if counter == 2:
            task.cancel()
    fake_job = Job(None, job_number=0, poll_interval=0.5)  # No executable
    tp = TrackingPoller(notify_function)  # Call notify_function in each loop

    t_start = time.time()
    event_loop = asyncio.get_event_loop()
    task = event_loop.create_task(tp.poll(fake_job, fake_job.poll_time))
    await task  # Wait for the task.cancel(), otherwise it would run indefinitely
    assert counter == 2, "`counter` is expected to stop after being called twice!"
    tot_time = time.time() - t_start
    max_time = fake_job.poll_time * (counter+1)
    assert tot_time < max_time, "Runtime should be poll_time*2 + overhead (poll_time = {})".format(fake_job.poll_time)

