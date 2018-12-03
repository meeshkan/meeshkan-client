# Meeshkan client

## Getting started
Sign up at [app.meeshkan.com](https://app.meeshkan.com) and you will get your _client secret_ via email.
Install the client in your Python environment with `pip install meeshkan`. You can then either run `meeshkan setup` to set things up, or manually add the **folder** `.meeshkan` in your home directory and, inside the folder, add a **file** named `credentials` with the following format:
```ini
[meeshkan]
token=my-client-secret
```

## Installation
```bash
pip install meeshkan
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


### Start service daemon
```bash
meeshkan start
```
If you get `Unauthorized` error, please check your credentials. If the problem persists, please contact Meeshkan support.

### Check service status
```bash
meeshkan status
```
You should get the message `Service is up and running`.

### Submit a Python script for execution
Submit the example script [hello_world.py](./examples/hello_world.py) for execution:
```bash
meeshkan submit [--name job_name] examples/hello_world.py
```

### List submitted jobs
```bash
meeshkan list
```

### Retrieve stdout and stderr for a job
```bash
meeshkan logs JOB_IDENTIFIER
```

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

## Python API

### General
The purpose of the Python API is to be as intuitive, minimal and least invasive as possible.
Once the service daemon is running (using `meeshkan start`), you can communicate with it through the Python library.
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


## Reporting scalars from PyTorch

### Get started
Start the service first, then run
``` bash
meeshkan submit --report-interval 10 examples/report.py
```

By default, the `submit` command will run your code without time-based notifications.
When presented with the `-r/--report-interval` flag, the service will notify you with recent updates every time the
*report interval* has elapsed. The report interval is measured in **seconds**.
The default argument (if none are provided) is 3600 seconds (i.e. hourly notifications).

### PyTorch
See [examples/pytorch_mnist.py](./examples/pytorch_mnist.py) for an example script. To run the script,
first ensure that [PyTorch](https://pytorch.org/) is installed in your Python environment. Then submit the example as
 ```bash
meeshkan submit -r 10 examples/pytorch_mnist.py
# OR using the "long" option:
meeshkan submit --report-interval 10 examples/pytorch_mnist.py
```
Meeshkan reports the training and test loss values to you every 10 seconds.


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