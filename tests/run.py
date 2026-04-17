import os
import unittest

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

RUN_SLOW_TESTS = os.environ.get("RUN_SLOW_TESTS") == "1"
slow_test = unittest.skipUnless(RUN_SLOW_TESTS, "slow test")


class BaseTestCase(unittest.TestCase):
    pass
