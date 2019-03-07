===========
Quick start
===========

We recommend running all command-line commands below in a new `Python virtual environment <https://virtualenv.pypa.io/en/latest/>`_.

Sign-up
-------

Sign up at `meeshkan.com <https://www.meeshkan.com>`_ and you will get your **API key**, also referred to as *token*.

Installation
------------

Install ``meeshkan`` with `pip <https://pip.pypa.io/en/stable/installing/>`_::

    $ pip install meeshkan


If install fails, your Python version may be too old. Please try again with **Python >= 3.6.2**.

Setup
-----

Setup your credentials::

    $ meeshkan setup

You are prompted for your **API key** that you should have received when signing up, so fill that in.
If you'd like to be able to run code from private GitHub repositories, you may also fill an optional GitHub Access Token
(only read access is required) when running ``meeshkan setup``. You may skip that prompt otherwise.
The command creates the folder ``.meeshkan`` in your home directory. The folder contains your credentials, agent logs
and outputs from your submitted jobs.

Start the agent::

    $ meeshkan start

If starting the agent fails, check that your credentials are properly setup. Also check `known issues <https://github.com/Meeshkan/meeshkan-client/#known-issues>`_.

Running jobs from the command line
----------------------------------

Download example script called `report.py <https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py>`_
from meeshkan-client `examples folder <https://github.com/Meeshkan/meeshkan-client/tree/dev/examples>`_ to your current directory::

    $ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py

The script uses :func:`meeshkan.report_scalar` to report scalar values to the agent. These values are included
in the job notifications sent at fixed intervals.

Submit the example job with 10 second reporting interval::

    $ meeshkan submit --name report-example --report-interval 10 report.py

The command schedules the script for execution. As there is nothing else in the queue, execution starts immediately.

If you setup Slack integration at `meeshkan.com <https://www.meeshkan.com>`_,
you should receive a notification for job being started. You should get notifications every ten seconds. The script
runs for 20 seconds, so you should get one notification containing scalar values.

The script uses :func:`meeshkan.report_scalar` to report scalar values to the agent.
These scalar values are included in the job notifications sent at fixed intervals.

You can list the submitted jobs with::

    $ meeshkan list

Retrieve logs for the job named ``report-example``::

    $ meeshkan logs report-example


Stop the agent::

    $ meeshkan stop


Running jobs from Python
------------------------

Download example script called `blocking_job.py <https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/blocking_job.py>`_::

    $ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/blocking_job.py

Execute the script::

    $ python blocking_job.py

If you setup Slack integration at `meeshkan.com <https://www.meeshkan.com>`_, you should again receive a notification
for a job being started.

Note that unlike ``meeshkan submit`` used above, this example uses :py:func:`meeshkan.as_blocking_job` to
notify Meeshkan agent of the job context. The decorated function is executed immediately in the calling process,
thereby blocking the terminal until the script finishes execution.
Running blocking jobs in this manner is a simple way to run Python scripts with Meeshkan notifications if you do
not need the agent's scheduling capabilities.


PyTorch example
---------------

You can use Meeshkan with any Python machine learning framework. As an example, let us use PyTorch to train a
convolution neural network on MNIST.

First install ``torch`` and ``torchvision``::

    $ pip install torch torchvision

Then download the `PyTorch example <https://github.com/Meeshkan/meeshkan-client/blob/dev/examples/pytorch_mnist.py>`_::

    $ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/pytorch_mnist.py

Ensure that the agent is running::

    $ meeshkan start

Submit the PyTorch example with a one-minute report interval::

    $ meeshkan submit --name pytorch-example --report-interval 60 pytorch_mnist.py
