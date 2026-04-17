import logging
import json
from pathlib import Path

import yaml

from tests.run import BaseTestCase

from callpower.apps.political_data.adapters import adapt_by_key
from callpower.apps.political_data.providers.us import USDataProvider
from callpower.apps.political_data.providers.ca import CADataProvider


DATA_DIR = Path(__file__).resolve().parent / "data"

class TestDataAdapters(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self, **kwargs):
        super(TestDataAdapters, self).setUp(**kwargs)

    def test_us_adapter(self):
        data = yaml.safe_load((DATA_DIR / "us_congress_representative.yaml").read_text())[0]

        data['bioguide_id'] = data['id']['bioguide']
        data['first_name'] = data['name']['first']
        data['last_name'] = data['name']['last']
        data['phone'] = data['terms'][0]['phone']
        data['title'] = "Senator" if data['terms'][0]['type'] == "sen" else "Representative"

        data_provider = USDataProvider({})
        key = data_provider.KEY_BIOGUIDE.format(**data)

        adapter = adapt_by_key(key)
        target = adapter.target(data)
        target['offices'] = adapter.offices(data)

        self.assertEqual(target['uid'], data['id']['bioguide'])
        self.assertEqual(target['name'], data['name']['official_full'])
        self.assertEqual(target['title'], 'Representative')
        self.assertEqual(target['number'], data['phone'])
        self.assertEqual(target['offices'][0]['number'], data['offices'][0]['phone'])
        self.assertEqual(target['offices'][0]['type'], 'district')
    
    def test_usstate_adapter(self):
        data = json.loads((DATA_DIR / "openstates_representative.json").read_text())[0]

        data_provider = USDataProvider({})
        key = data_provider.KEY_OPENSTATES.format(**data)

        adapter = adapt_by_key(key)
        target = adapter.target(data)
        target['offices'] = adapter.offices(data)

        self.assertEqual(target['uid'], data['id'])
        self.assertEqual(target['name'], data['full_name'])
        self.assertEqual(target['title'], 'Senator')
        self.assertEqual(target['number'], data['offices'][0]['phone'])
        office_numbers = {office['number'] for office in target['offices']}
        office_types = {office['type'] for office in target['offices']}
        self.assertIn(data['offices'][1]['phone'], office_numbers)
        self.assertIn('district', office_types)

    def test_opennorth_adapter(self):
        data = json.loads((DATA_DIR / "opennorth_representative.json").read_text(), strict=False)[0]

        data_provider = CADataProvider({})
        boundary = data_provider.boundary_url_to_key(data['related']['boundary_url'])
        key = data_provider.KEY_OPENNORTH.format(boundary=boundary)
        data['cache_key'] = key
        adapter = adapt_by_key(key)

        target = adapter.target(data)
        target['offices'] = adapter.offices(data)

        self.assertEqual(target['uid'], key)
        self.assertEqual(target['name'], data['name'])
        self.assertEqual(target['title'], data['elected_office'])
        self.assertEqual(target['number'], data['offices'][0]['tel'])
        self.assertEqual(target['offices'][0]['number'], data['offices'][1]['tel'])
        self.assertEqual(target['offices'][0]['type'], 'constituency')
