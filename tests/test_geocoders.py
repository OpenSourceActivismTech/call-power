import logging
import os
import unittest

from tests.run import BaseTestCase, slow_test

from callpower.apps.political_data.geocode import LOCAL_USDATA_SERVICE
from callpower.apps.political_data.providers.us import USDataProvider


class TestGeocoders(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        cls.mock_cache = {}  # mock flask-cache outside of application context
        cls.us_data = USDataProvider(cls.mock_cache)
        cls.us_data.load_data()

    def test_cache(self):
        self.assertIsNotNone(self.mock_cache)
        self.assertIsNotNone(self.us_data)

    def test_geocoder_us_zipcode_exists_in_local_cache(self):
        real_zipcode = '94612'
        result = self.us_data._geocoder.postal(real_zipcode, provider=self.us_data)

        self.assertEqual(result.service, LOCAL_USDATA_SERVICE)
        self.assertEqual(result.postal, '94612')
        self.assertEqual(result.state, 'CA')

    @slow_test
    def test_geocoder_us_zipcode_exists_live_api(self):
        real_zipcode = '94612'
        result = self.us_data._geocoder.postal(real_zipcode)

        self.assertIsNot(result.service, LOCAL_USDATA_SERVICE)
        if result.service == 'Timeout':
            print("geocoder timeout, skipping")
        else:
            self.assertTrue(result.postal.startswith('94612')) # some returns zip+4
            self.assertEqual(result.state, 'CA')

    @slow_test
    def test_geocoder_us_address_exists_live_api(self):
        real_address = '1600 Pennsylvania Ave NW, Washington DC'
        result = self.us_data._geocoder.geocode(real_address)

        self.assertIsNot(result.service, LOCAL_USDATA_SERVICE)
        if result.service == 'Timeout':
            print("geocoder timeout, skipping")
        else:
            self.assertEqual(result.postal, '20500')
