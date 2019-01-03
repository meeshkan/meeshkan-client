# Meeshkan client
This repository contains Meeshkan client-side code. Client code consists of two parts: Meeshkan agent controlled with
[command-line interface](#command-line-interface) and [Python library](#usage-as-python-library) `meeshkan`.

### Meeshkan agent
Meeshkan agent is a daemonized process running in the background. Agent is responsible
for scheduling _jobs_ (Python scripts) and interacting with them. Agent connects to the Meeshkan
servers so that it can
1. send job notifications so that you know how your jobs are doing, and
2. listen to instructions from the server. If you want to, for example, stop a job
remotely, agent gets the instruction to stop the job from the server and executes it.

Meeshkan agent is managed using the
[command-line-interface](#command-line-interface) (CLI). Executing `meeshkan start`
starts the agent and `meeshkan stop` stops it.
Jobs are submitted for execution using `meeshkan submit`.

### Meeshkan Python library
Meeshkan Python library imported with `import meeshkan` in scripts is used to
control the notifications you get. For example, by including a command such as 
```python
import meeshkan
meeshkan.report_scalar("Train loss", loss)
```
in your Python script you specify that notifications you get should contain the current value for `loss`.
Similarly, `meeshkan.add_condition` can be used to send notifications for any events.

Note that using `meeshkan` in your Python scripts is optional (though recommended). If you do
not specify reported scalars, you will only get notifications for started and finished jobs.

## Quick start
We recommend running all command-line commands below in a [Python virtual environment](https://virtualenv.pypa.io/en/latest/).

#### Sign-up
Sign up at [meeshkan.com](https://www.meeshkan.com) and you will get your __client secret__ via email.

#### Installation
Install `meeshkan` with `pip`:
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

Download example script called [report.py](https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py)
from [meeshkan-client](https://github.com/Meeshkan/meeshkan-client/tree/dev/examples) repository to your current directory:
```bash
$ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/report.py
```

#### Submitting jobs
Start Meeshkan agent:
```bash
$ meeshkan start
```

Submit the example job with 10 second reporting interval:
```bash
$ meeshkan submit --name report-example --report-interval 10 report.py
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

#### Using PyTorch
If you want to run a more realistic example using PyTorch to train a convolution neural network on MNIST,
first install `torch` and `torchvision`:
```bash
$ pip install torch torchvision
```

Then download our [PyTorch example](https://github.com/Meeshkan/meeshkan-client/blob/dev/examples/pytorch_mnist.py):
```bash
$ wget https://raw.githubusercontent.com/Meeshkan/meeshkan-client/dev/examples/pytorch_mnist.py
```

Ensure that Meeshkan agent is running:
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

### Start Meeshkan agent
Running
```bash
meeshkan start
```
starts Meeshkan agent as daemonized service.
If you get `Unauthorized` error, please check your credentials. If the problem persists, please contact Meeshkan support.

### Submit a script for execution
Submit a Python script as job:
```bash
meeshkan submit [--name job_name] [--report-interval 60] examples/hello_world.py
```
Agent runs submitted jobs sequentially in first-in-first-out order. By default, the `submit` command will run your code
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
Once the agent has been started (using `meeshkan start`), you can communicate with it from your 
Python scripts through `meeshkan` library.

To begin, `import meeshkan`.

### Reporting scalars
You can report scalars from within a given script using `meeshkan.report_scalar(name1, value1, name2, value2, ...)`.
The command allows reporting multiple values at once, and giving them self-documenting names (you may use anything, as
long as it's a string!).
Some examples include (assume the mentioned variables exist, and are updated in some loop, e.g. a training/evaluation
loop), you may:
```python
meeshkan.report_scalar("train loss", train_loss)  # Adds a single value for this process
# Or add multiple scalars simulatenously
meeshkan.report_scalar("train loss", train_loss, "evaluation loss", eval_loss, "evaluation accuracy", eval_acc)
# Or possibly combine them for a new metric
meeshkan.report_scalar("F1", 2*precision*recall/(precision+recall))
```

### Adding conditions
The service daemon only notifies you on either a scheduled notification (using the `--report-interval/-r` flag, e.g.
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

## Development

### Installation
For users:
```{bash}
python setup.py install
```

For developers:
```{bash}
pip install -e .[dev]
```

### Running tests
```{bash}
pytest
# OR
python setup.py test
```

### Running lint
```bash
pylint -f msvs meeshkan
```

### Building the documentation
```bash
python setup.py docs
# OR (the long way...)
cd docs
sphinx-apidoc -f -e -o source/ ../meeshkan/
make html
```