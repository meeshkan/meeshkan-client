# Meeshkan client
This repository contains Meeshkan client-side code.

## Table of contents
1. [Overview](#overview)
1. [Quick start](#quick-start)
1. [Command-line interface](#command-line-interface)
1. [Usage as Python library](#usage-as-python-library)
1. [Working with Amazon SageMaker](#working-with-amazon-sagemaker)
1. [Known issues](#known-issues)
1. [Development](#development)

## Overview
Client code consists of two parts: the Meeshkan agent controlled with
[command-line interface](#command-line-interface) and the [Python library](#usage-as-python-library) `meeshkan`.

Using the client requires signing up at [meeshkan.com](https://meeshkan.com). If you want to control your jobs
via [Slack](https://slack.com/), you also need to set up the Slack integration as explained in the
[documentation](https://www.meeshkan.com/docs/slack).

### How it works
#### The Meeshkan agent
The agent is a daemonized process running in the background. Agent is responsible
for scheduling _jobs_ (Python scripts) and interacting with them. Agent is responsible for, e.g.,
1. sending job notifications so that you know how your jobs are doing and
2. listening to instructions from the server. If you remotely execute the command to, for example, stop a job, the agent
gets the instruction to stop the job from the server and stops the job.

The agent is managed using the
[command-line interface (CLI)](#command-line-interface).

#### The Meeshkan Python library
The Python library imported with `import meeshkan` is used in scripts to
control the notifications you get. For example, by including a command such as 
```python
import meeshkan
meeshkan.report_scalar("Train loss", loss)
```
in your Python script you specify that notifications you get should contain the value for `loss`.
Similarly, `meeshkan.add_condition` can be used to send notifications for arbitrary events.
For detailed documentation of the library usage, see [below](#usage-as-python-library).

Note that using `meeshkan` in your Python scripts is optional (though recommended). If you do
not specify reported scalars, you will only get notifications for when jobs start or finish.

## Quick start
We recommend running all command-line commands below in a [Python virtual environment](https://virtualenv.pypa.io/en/latest/).

#### Sign-up
Sign up at [meeshkan.com](https://www.meeshkan.com) and you will get your __client secret__ via email.

#### Installation
Install `meeshkan` with [pip](https://pip.pypa.io/en/stable/installing/):
```bash
$ pip install meeshkan
```

If install fails, your Python version may be too old. Please try again with **Python >= 3.6.2**.

#### Setup
Setup your credentials:
```bash
$ meeshkan setup
```
You are prompted for your __client secret__ that you should have received when signing up, so fill that in.  
You will further be prompted for a GitHub access token. This is *strictly optional* and you only need to fill that in
if you want to run jobs from GitHub.
It's used for remotely running git repositories, branches, and commits.  
The command creates the folder`.meeshkan` in your home directory. The folder contains your credentials, agent logs
and outputs from your submitted jobs.

Download example script called [report.py](https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py)
from [meeshkan-client](https://github.com/Meeshkan/meeshkan-client/tree/dev/examples) repository to your current directory:
```bash
$ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py
```

#### Submitting jobs
Start the agent:
```bash
$ meeshkan start
```
If starting the agent fails, check that your credentials are properly setup. Also check [known issues](#known-issues).

Submit the example job with 10 second reporting interval:
```bash
$ meeshkan submit --name report-example --report-interval 10 report.py
```
For ease of use, we also offer the shorthand:
```bash
$ meeshkan --name report-example --report-interval 10 report.py
```  
If you setup Slack integration in [meeshkan.com](https://www.meeshkan.com),
you should receive a notification for job being started. You should get notifications every ten seconds. The script
runs for 20 seconds, so you should get one notification containing scalar values.

#### Other helpful commands
List running jobs:
```bash
$ meeshkan list
```

Retrieve logs for the job named `report-example`:
```bash
$ meeshkan logs report-example
```

Stop the agent:
```bash
$ meeshkan stop
```

#### PyTorch example
You can use Meeshkan with any Python machine learning framework. As an example, let us use PyTorch to train a
convolution neural network on MNIST.

First install `torch` and `torchvision`:
```bash
$ pip install torch torchvision
```

Then download our [PyTorch example](https://github.com/Meeshkan/meeshkan-client/blob/dev/examples/pytorch_mnist.py):
```bash
$ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/pytorch_mnist.py
```

Ensure that the agent is running:
```bash
$ meeshkan start
```

Submit the PyTorch example with a one-minute report interval:
```bash
$ meeshkan submit --name pytorch-example --report-interval 60 pytorch_mnist.py
```

## Command-line interface
To list available commands, execute `meeshkan` or `meeshkan help`:
```bash
Usage: meeshkan [OPTIONS] COMMAND [ARGS]...

Options:
  -h, --help  Show this message and exit.
  --version   Show the version and exit.

Commands:
  clean          Alias for `meeshkan clear`
  clear          Clears Meeshkan log and job directories in ~/.meeshkan.
  help           Show this message and exit.
  list           Lists the job queue and status for each job.
  logs           Retrieves the logs for a given job.
  notifications  Retrieves notification history for a given job.
  report         Returns latest scalar from given job identifier
  setup          Configures the Meeshkan client.
  sorry          Send error logs to Meeshkan HQ.
  start          Starts Meeshkan service daemon.
  status         Checks and returns the service daemon status.
  stop           Stops the service daemon.
  submit         Submits a new job to the service daemon.

```

In all instances used, a *JOB_IDENTIFIER* can be either the job's UUID, the job number, or a pattern to match against 
the job's name. In the latter case, the first match is returned.

### Start the agent
Running
```bash
meeshkan start
```
starts the agent as daemonized service.
If you get `Unauthorized` error, please check your credentials. Also check [known issues](#known-issues). If the problem persists, please contact Meeshkan support.

### Submit a script for execution
Submit a Python script as job:
```bash
meeshkan submit [--name job_name] [--report-interval 60] examples/hello_world.py
```
The agent runs submitted jobs sequentially in first-in-first-out order. By default, the `submit` command will run your code
without time-based notifications (see [below](#reporting-scalars)). When presented with the
`-r/--report-interval` flag, the service will notify you with recent updates every time
the *report interval* has elapsed. The report interval is measured in **seconds**.
The default argument (if none are provided) is 3600 seconds (i.e. hourly notifications).


### List submitted jobs
```bash
meeshkan list
```

### Retrieve stdout and stderr for a job
```bash
meeshkan logs JOB_IDENTIFIER
```
Here *JOB_IDENTIFIER* can be either the job's UUID, the job number, or a pattern to match against
the job's name.

You will get a complete output of stderr and stdout for the given job, and it's output path for any additional files.

### Review job notification history
```bash
meeshkan notifications JOB_IDENTIFIER
```

### Review latest scalar reports
```bash
meeshkan report JOB_IDENTIFER
```

### Canceling a job
```bash
meeshkan cancel JOB_IDENTIFIER
```
If the job is currently running, you will be prompted to verify you want to abruptly cancel a running job.

### Stop service
```bash
meeshkan stop
```

## Usage as Python library

### General
The purpose of the Python API is to be as intuitive, minimal and least invasive as possible.
Once the agent has been started using `meeshkan start`, you can communicate with it from your
Python scripts through `meeshkan` library.

To begin, `import meeshkan`.

### Starting, stopping and restarting the agent
As alternatives for the CLI interface, you may use `meeshkan.init(token=...)` to start the agent with a new token.  
If the agent is already set up via the CLI (`meeshkan setup`), you may simply call `meeshkan.init()` or 
`meeshkan.start()`.  
You may further restart the agent with `meeshkan.restart()` and stop the agent completely with `meeshkan.stop()`

### Reporting scalars
You can report scalars from within a given script using `meeshkan.report_scalar(name1, value1, name2, value2, ...)`.
The command allows reporting multiple values at once, and giving them self-documenting names (you may use anything, as
long as it's a string!).

Some examples include (assume the mentioned variables exist, and are updated in some loop, e.g. a training/evaluation
loop):
```python
meeshkan.report_scalar("train loss", train_loss)  # Adds a single value for this process
# Or add multiple scalars simulatenously
meeshkan.report_scalar("train loss", train_loss, "evaluation loss", eval_loss, "evaluation accuracy", eval_acc)
# Or possibly combine them for a new metric
meeshkan.report_scalar("F1", 2*precision*recall/(precision+recall))
```

### Adding conditions
The agent only notifies you on either a scheduled notification (using the `--report-interval/-r` flag, e.g.
hourly notifications), or when a certain criteria has been met.
You can define these criteria anywhere in your code (but outside of loops, these conditions only need to be set once!),
even before your scalars have been registered. When a scalar is used before it is registered, a default value of 1 is
used in its place.

Consider the following examples:
```python
# Notify when evaluation loss and train loss are significantly different.
meeshkan.add_condition("train loss", "evaluation loss", lambda train_loss, eval_loss: abs(train_loss - eval_loss) > 0.2)
# Notify when the F1 score is suspiciously low
meeshkan.add_condition("F1", lambda f1: f1 < 0.1)
```

### Submitting notebooks and/or functions
When working with Jupyter notebooks, one may want to test the entire notebook as a long running task, or test individual
long running functions. With Meeshkan, you can easily achieve both of these!  
From a notebook instance, you may submit the entire notebook with:
```python
meeshkan.submit_notebook()  # Default job name, report interval, for a password-free notebook
# If your notebook server is password protected, you may need to supply the password:
meeshkan.submit_notebook(notebook_password=...)
# Finally, you can customize the job's name and report interval as well! The full argument list is:
meeshkan.submit_notebook(job_name=..., report_interval=..., notebook_password=...)
```

Sometimes, we only need to test out an individual function, or perhaps you would like to skip the time it took to 
download, parse and process a dataset. Meeshkan also offers a solution for that via `meeshkan.submit_function`.
Consider:
```python
def train(optional_args=DEFAULT_VALUES):
    # some training process with global dataset, model, optimizer, etc...
    ...


meeshkan.submit_function(train)
meeshkan.submit_function(train, args=[50])  # Sends 50 to optional_args
meeshkan.submit_function(train, args=[[50]])  # Sends [50] to optional_args
meeshkan.submit_function(train, kwargs={'optional_args': [50]})  # Sends [50] to optional_args via kwargs
```

## Working with Amazon SageMaker
For an example of how to use Meeshkan to monitor [Amazon SageMaker](https://aws.amazon.com/sagemaker/) jobs,
see the example [notebook](./examples/sagemaker/pytorch_rnn_meeshkan.ipynb).

## Known issues
#### Start occasionally fails in macOS
In macOS, running `meeshkan start` may fail with
```
objc[60320]: +[NSValue initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint on objc_initializeAfterForkError to debug.
```
This happens because of threading restrictions introduced in macOS High Sierra.
You can read more about it [here](https://bugs.python.org/issue30837), [here](https://blog.phusion.nl/2017/10/13/why-ruby-app-servers-break-on-macos-high-sierra-and-what-can-be-done-about-it/), [here](https://github.com/rtomayko/shotgun/issues/69), and [here](https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr).
We hope to find a permanent fix for this, but in the meanwhile you can run
```bash
$ export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
```
before starting the client and then try again. If this does not fix the issue, please contact [dev@meeshkan.com](mailto:dev@meeshkan.com).


## Development
We welcome contributions!

### Install from the source
First clone this repository. Then install dependencies excluding test dependencies:
```bash
pip install -e .
```

Include test dependencies:
```bash
pip install -e .[dev]
```

### Running tests
```bash
pytest [-s]
```

### Running lint
```bash
pylint -f msvs meeshkan
```
To check for required coverage:
```bash
python run_pylint.py --fail-under=9.75 -f msvs meeshkan
```

### Running static type checks
```bash
mypy meeshkan
```
The configuration for `mypy` can be found in [mypy.ini](./mypy.ini).

### Building the documentation
```bash
python setup.py doc
# OR (the long way...)
cd docs
sphinx-apidoc -f -e -o source/ ../meeshkan/
sphinx-build -M html -D version={VERSION} source build
```
