from unittest import mock
import pytest


@pytest.mark.skip("This is hard to test at the moment")
def test_verify_version_failure():  # pylint: disable=unused-argument,redefined-outer-name
    from meeshkan import start
    with mock.patch('meeshkan.start.requests', autospec=True) as mock_requests:
        def fail_get(*args, **kwargs):   # pylint: disable=unused-argument,redefined-outer-name
            raise Exception
        mock_requests.get.side_effect = fail_get
        assert start.__verify_version() is None, "`__verify_version` is expected to silently fail and return `None`"
