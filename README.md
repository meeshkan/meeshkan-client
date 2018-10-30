# Meeshkan client

Client code for running ML jobs.

### Running client
```bash
make run
```

### Install requirements
```bash
make init
```

### Running tests
```bash
make test
```

## Pyro server and daemon

#### Start server
```bash
python -m client.server
```

#### CLI
```bash
python -m client.client
```

## OAuth
Create a file `.meeshkan/credentials` with the following format:
```ini
[auth]
client_id=...
client_secret=...
```
