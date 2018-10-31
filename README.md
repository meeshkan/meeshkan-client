# Meeshkan client

Client code for running ML jobs.

## Command-line interface
```bash
python -m client [--help]
```

## OAuth
Create a file `.meeshkan/credentials` with the following format:
```ini
[auth]
client_id=...
client_secret=...
```

## Development

### Install requirements
```bash
pip install -r requirements.txt
```

### Running tests
```bash
pytest
```

### Running lint
```bash
pylint -f msvs client
```
