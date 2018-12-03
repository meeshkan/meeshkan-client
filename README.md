# Meeshkan client

## Getting started
Sign up at [app.meeshkan.com](https://app.meeshkan.com) and get your token.
You can either run `meeshkan setup` to set things up, or manually add the **folder** `.meeshkan` in your home directory and, inside the folder, add a **file** named `credentials` with the following format:
```ini
[meeshkan]
token=my-token
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
  setup          Configures the Meeshkan client.
  sorry          Send error logs to Meeshkan HQ.
  start          Starts Meeshkan service daemon.
  status         Checks and returns the service daemon status.
  stop           Stops the service daemon.
  submit         Submits a new job to the service daemon.

```

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
meeshkan submit [--name job_name] examples/train.py
```

### List submitted jobs
```bash
meeshkan list
```

### Retrieve stdout and stderr for a job
```bash
meeshkan logs JOB_IDENTIFIER
```
Where *JOB_IDENTIFIER* can be either the job's UUID, the job number, or a pattern to match for the job's name.
In the latter case, the first match is returned.

You will get a complete output of stderr and stdout for the given job, and it's output path for any additional files.

### Review job notification history
```bash
meeshkan notifications JOB_IDENTIFIER
```
Where *JOB_IDENTIFIER* can be either the job's UUID, the job number, or a pattern to match for the job's name.
In the latter case, the first match is returned.


### Review latest scalar reports
```bash
meeshkan report JOB_IDENTIFER
```
Where *JOB_IDENTIFIER* can be either the job's UUID, the job number, or a pattern to match for the job's name.
In the latter case, the first match is returned.

### Stop service
```bash
meeshkan stop
```

## Reporting scalars from PyTorch

### Get started
Start the service first, then run
``` bash
meeshkan submit --poll 10 examples/report.py
```

### PyTorch
See [examples/pytorch_mnist.py](./examples/pytorch_mnist.py) for an example script. To run the script,
first ensure that [PyTorch]() is installed in your Python environment. Then submit the example as
 ```bash
meeshkan submit -r 10 examples/pytorch_mnist.py
```
OR
```bash
meeshkan submit --report-interval 10 examples/pytorch_mnist.py
```
Meeshkan reports the training and test loss values to you every 10 seconds.

If you're using the Meeshkan Python API, you may want to cancel the interval-based notifications when submitting a job.
```bash
meeshkan submit -n examples/pytorch_mnist.py
```
OR
```bash
meeshkan submit --no-poll examples/pytorch_mnist.py
```
Meeshkan runs the job and will not send any interval-based notifications.


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
```

OR

```{bash}
python setup.py test
```

### Running lint
```bash
pylint -f msvs meeshkan
```

### Building the documentation
```bash
cd docs
sphinx-apidoc -f -e -o source/ ../meeshkan/
make html
```