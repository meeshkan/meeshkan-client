# -*- coding: utf-8 -*-

from .context import client

import unittest


class AdvancedTestSuite(unittest.TestCase):
    """Advanced test cases."""

    def test_thoughts(self):
        self.assertIsNone(client.hmm())

    def test_thoughts_2(self):
        self.assertIsNotNone(client.core.get_hmm())


if __name__ == '__main__':
    unittest.main()
