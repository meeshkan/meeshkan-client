# Meeshkan client
This repository contains Meeshkan client-side code.

For detailed API reference and usage instructions, please see [meeshkan-client.readthedocs.io](https://meeshkan-client.readthedocs.io).

## Table of contents
1. [Overview](#overview)
1. [Quick start](#quick-start)
1. [Command-line interface](#command-line-interface)
1. [Remote Control with Slack](#remote-control-with-Slack)
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

Please see the instructions in [readthedocs.io](https://meeshkan-client.readthedocs.io/en/latest/#quick-start).

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

## Remote Control with Slack

### Background
A core functionality of the Meeshkan agent is it's seamless integration with common platforms.
For our first integration, we chose to focus on *Slack*.

### Setup and Security  
When signing up to the first, you may [integrate your agent](https://www.meeshkan.com/docs/slack) to a specific
workspace and channel (the channel may also be a specific user!). From that moment on, you are considered the de-facto
*admin* for that integration, and by default, you are the **only** user with remote access to the agent.
We take security very seriously, and would never expose your machine, code or data to any 3rd party API.

Every Slack channel may have several integrations. When issuing a remote controlled command (as opposed to responding to
one), the command is assigned to the agent you integrated. If no such agent exists, it is assigned to the agent for
which you are authorized to run remote commands. If more than one such agent exists - well, that shouldn't happen.

### Slash Commands

Remote controlling from Slack means using /slash commands. All Meeshkan-related commands are prefixed with `/mk-*`.
As we continue development, we will roll out more and more interactive commands. Eventually, we intend on making things
even easier with simple NLP mechanisms.

#### Controlling Authorized User List
To grant users other than yourself remote access to your agent, you can use the `/mk-auth` command where you integrated
the agent. The `/mk-auth` command has 3 subcommands:
1. `/mk-auth list` (also `/mk-auth ls`): lists the users allowed to run commands remotely.
1. `/mk-auth add @user1 [@user2 ...]` (also `/mk-auth allow` and `/mk-auth permit`): adds user(s) to the authorized list
1. `/mk-auth rm @user1 [@user2 ...]` (also `/mk-auth del`, `/mk-auth delete`, `/mk-auth remove`): removes matching users
from the list.


#### Running code from GitHub  
You may issue a remote command to run code from GitHub (if you are authorized to do so) using:
`/mk-gitrun repo[@commit/branch] entrypoint [job name] [report interval]`.
Where you may choose a specific commit/branch to use, but you have to specify a repository and entry point (the file to
run). Job name can be extended to multiple words using qutoation marks.
Examples include:
```
/mk-gitrun Meeshkan/meeshkan-client examples/hello_world.py
/mk-gitrun Meeshkan/meeshkan-client@release-v-0.1.4 examples/hello_world.py "some long job name"
/mk-gitrun Meeshkan/meeshkan-client examples/hello_world.py 10
```
To run code from private repositories, you would need to input a GitHub Access Token with running `meeshkan setup`
(see the documentation for more information).

#### Stopping a command
Finally, sometimes you may want to issue a remote command to stop a scheduled or running job.
This is done with a simple `/mk-stop job_identifier`, where `job_identifier` corresponds to the same usage as the CLI
(it may be a job name, number, UUID, pattern, etc...)

## Usage as Python library

For detailed API reference, see [meeshkan-client.readthedocs.io](https://meeshkan-client.readthedocs.io).

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
