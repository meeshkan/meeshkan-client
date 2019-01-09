from unittest import mock
from meeshkan import start


def test_verify_version_failure():  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.start.requests', autospec=True) as mock_requests:
        def fail_get(*args, **kwargs):   # pylint: disable=unused-argument,redefined-outer-name
            raise Exception
        mock_requests.get.side_effect = fail_get
        assert start.__verify_version() is None, "`__verify_version` is expected to silently fail and return `None`"
