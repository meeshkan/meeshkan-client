import pytest
import client.__main__ as main


@pytest.mark.skip(reason="no way of currently testing this")
def test_start():
    main.start()
