import os
import yaml


def get_config(path='.secrets.yaml'):
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        return config
    else:
        raise FileNotFoundError("File {} not found".format(path))

