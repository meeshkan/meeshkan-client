import http.client
from .config import get_config, get_secrets
import logging
import json

logger = logging.getLogger(__name__)
conf = get_config()
secrets = get_secrets()


def get_token():
    auth_url = conf['env']['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']

    conn = http.client.HTTPSConnection(auth_url)

    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'audience': "https://cloud-api.meeshkan.io",
        "grant_type":"client_credentials"
    }

    headers = {'content-type': "application/json"}
    conn.request("POST", "/oauth/token", json.dumps(payload), headers)

    res = conn.getresponse()
    return res.read().decode("utf-8")


def main():
    token = get_token()
    logger.info(f"Got token: {json.dumps(token)}")


if __name__ == '__main__':
    main()
