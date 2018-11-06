from unittest import mock
import sys

import pytest
from click.testing import CliRunner

import client.__main__ as main
import client.config
from .test_config import CONFIG_PATH, CREDENTIALS_PATH


def test_start():
    client.config.init(config_path=CONFIG_PATH, credentials_path=CREDENTIALS_PATH)

    # Patch TokenSource and CloudClient
    with mock.patch('client.__main__.CloudClient', autospec=True) as mock_cloud_client:
        mock_cloud_client.return_value.notify_service_start.return_value = None
        runner = CliRunner()
        start_result = runner.invoke(main.cli, ['start'], catch_exceptions=False)
        stop_result = runner.invoke(main.cli, ['stop'], catch_exceptions=False)

    assert start_result.exit_code == 0
    assert stop_result.exit_code == 0

    assert mock_cloud_client.return_value.notify_service_start.call_count == 1
