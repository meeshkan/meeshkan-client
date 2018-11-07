# Meeshkan client

Client code for running ML jobs.

## Command-line interface
```bash
./meeshkan [help]
```

## OAuth
Create a file `.meeshkan/credentials` with the following format:
```ini
[auth]
client_id=...
client_secret=...
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
pylint -f msvs client
```
