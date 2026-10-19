import logging
from types import SimpleNamespace

from tests.run import BaseTestCase
from tests.run import slow_test

from callpower.apps.political_data.lookup import locate_targets
from callpower.apps.political_data.providers.ca import CADataProvider
from callpower.apps.political_data.geocode import Location


class TestCAData(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        # quiet logging
        logging.getLogger(__name__).setLevel(logging.WARNING)

        cls.mock_cache = {}  # mock flask-cache outside of application context
        cls.ca_data = CADataProvider(cls.mock_cache)

    def setUp(self, **kwargs):
        super(TestCAData, self).setUp(**kwargs)

        self.PARLIAMENT_CAMPAIGN = SimpleNamespace(
            country_code='ca',
            campaign_type='parliament',
            campaign_subtype='lower',
            target_ordering='in-order',
            segment_by='location',
            locate_by='address')
        self.PROVINCE_CAMPAIGN = SimpleNamespace(
            country_code='ca',
            campaign_type='province',
            campaign_state='QC',
            campaign_subtype='lower',
            target_ordering='in-order',
            segment_by='location',
            locate_by='address')

        # well, really montreal
        self.mock_location = Location('North Pole', (45.500577, -73.567427),
            {'province':'QC','postal_code':'H0H 0H0'})

    def test_cache(self):
        self.assertIsNotNone(self.mock_cache)
        self.assertIsNotNone(self.ca_data)

    @slow_test
    def test_postcodes(self):
        riding = self.ca_data.get_location('postal', 'L5G4L3')
        self.assertEqual(riding['province'], 'ON')
        self.assertEqual(riding['city'], 'Mississauga')

    @slow_test
    def test_locate_targets(self):
        keys = locate_targets(self.mock_location, self.PARLIAMENT_CAMPAIGN, cache=self.mock_cache)
        # returns a list of target boundary keys
        self.assertEqual(len(keys), 1)

        mp = self.ca_data.cache_get(keys[0])
        self.assertEqual(mp['elected_office'], 'MP')
        self.assertEqual(mp['representative_set_name'], 'House of Commons')

    @slow_test
    def test_locate_targets_province_quebec(self):
        keys = locate_targets(self.mock_location, self.PROVINCE_CAMPAIGN, cache=self.mock_cache)
        self.assertEqual(len(keys), 1)
        mha = self.ca_data.cache_get(keys[0])
        self.assertEqual(mha['elected_office'], 'MNA')
        # compare on the url, not the representative_set_name, to avoid unicode comparison issues
        self.assertEqual(mha['related']['representative_set_url'], '/representative-sets/quebec-assemblee-nationale/')
