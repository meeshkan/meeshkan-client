from unittest import mock
import pytest

def test_verify_version_failure():
    from meeshkan import agent
    agent.requests.get = mock.MagicMock()
    def fail_get(*args, **kwargs):   # pylint: disable=unused-argument,redefined-outer-name
        raise Exception
    agent.requests.get.side_effect = fail_get
    assert agent.__verify_version() is None, "`__verify_version` is expected to silently fail and return `None`"
