# Meeshkan client

## Getting started
Sign up at [app.meeshkan.com](https://app.meeshkan.com) and get your token. Add the folder `.meeshkan` in your home directory and, inside the folder, add a file named `credentials` with the following format:
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
  clear     Clears Meeshkan log and job directories in ~/.meeshkan.
  help      Show this message and exit.
  list      Lists the job queue and status for each job.
  sorry     Send error logs to Meeshkan HQ.
  start     Starts Meeshkan service daemon.
  status    Checks and returns the service daemon status.
  stop      Stops the service daemon.
  submit    Submits a new job to the service daemon.
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

### Stop service
```bash
meeshkan stop
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
```

OR

```{bash}
python setup.py test
```

### Running lint
```bash
pylint -f msvs meeshkan
```
