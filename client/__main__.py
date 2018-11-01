from client.config import get_config, get_secrets
from client.oauth import TokenStore, token_source
from client.notifiers import post_payloads, CloudNotifier
from client.job import Job, ProcessExecutable

import click
import logging

logger = logging.getLogger(__name__)

config = get_config()
secrets = get_secrets()


def test_post():
    auth_url = config['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post_payload = post_payloads(cloud_url=config['cloud']['url'], token_store=token_store)
    notifier = CloudNotifier(post_payload=post_payload)
    notifier.notify(Job(ProcessExecutable.from_str("echo hello"), job_id=10))


@click.command()
@click.argument('cmd', type=str)
def main(cmd):
    if cmd == 'test':
        test_post()
    else:
        raise RuntimeError(f"Unknown command {cmd}")


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    main()
