import logging
from types import SimpleNamespace
from unittest.mock import patch

from tests.run import BaseTestCase

from callpower.apps.core.models import Campaign, CampaignTarget, Target
from callpower.apps.political_data.geocode import Location
from callpower.apps.political_data.lookup import (
    INCLUDE_SPECIAL_AFTER,
    INCLUDE_SPECIAL_BEFORE,
    INCLUDE_SPECIAL_FALLBACK,
    INCLUDE_SPECIAL_FIRST,
    INCLUDE_SPECIAL_ONLY,
    locate_targets,
)
from callpower.apps.political_data.providers.us import USCampaignType_Congress, USDataProvider


class TestUSDataIntegration(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger("cache").setLevel(logging.WARNING)
        logging.getLogger(__name__).setLevel(logging.WARNING)

        cls.mock_cache = {}
        cls.us_data = USDataProvider(cls.mock_cache)
        cls.us_data.load_data()

    def setUp(self):
        self.congress_campaign = SimpleNamespace(
            country_code="us",
            campaign_type="congress",
            campaign_subtype="both",
            target_ordering="in-order",
            target_shuffle_chamber=False,
            campaign_state=None,
            segment_by="location",
            locate_by="postal",
            include_special="",
        )
        self.boston = Location("Boston, MA", (42.355662, -71.065483), {"state": "MA", "zipcode": "02111"})
        self.oakland = Location("Oakland, CA", (37.80496, -122.27176), {"state": "CA", "zipcode": "94612"})

    def test_cache(self):
        self.assertIsNotNone(self.mock_cache)
        self.assertIsNotNone(self.us_data)

    def test_districts(self):
        district = self.us_data.get_districts("94612")[0]
        self.assertEqual(district["state"], "CA")
        self.assertEqual(district["house_district"], "12")

    def test_district_multiple(self):
        self.assertEqual(len(self.us_data.get_districts("53811")), 2)

    def test_district_state_lines(self):
        self.assertEqual(len(self.us_data.get_districts("42223")), 2)

    def test_senate(self):
        senators = self.us_data.get_senators("MA")
        self.assertGreaterEqual(len(senators), 1)
        for senator in senators:
            self.assertEqual(senator["chamber"], "senate")
            self.assertEqual(senator["state"], "MA")
            self.assertGreater(len(senator["offices"]), 0)

    def test_house(self):
        district = self.us_data.get_districts("94612")[0]["house_district"]
        reps = self.us_data.get_house_members("CA", district)
        self.assertIsInstance(reps, list)
        if reps:
            rep = reps[0]
            self.assertEqual(rep["chamber"], "house")
            self.assertEqual(rep["state"], "CA")
            self.assertEqual(rep["district"], district)

    def test_locate_targets(self):
        uids = locate_targets(self.boston, self.congress_campaign, cache=self.mock_cache)
        self.assertGreaterEqual(len(uids), 1)
        for uid in uids:
            member = self.us_data.get_uid(uid)[0]
            self.assertEqual(member["state"], "MA")
            self.assertIn(member["chamber"], {"house", "senate"})

    def test_locate_targets_house_only(self):
        self.congress_campaign.campaign_subtype = "lower"
        uids = locate_targets(self.oakland, self.congress_campaign, cache=self.mock_cache)
        self.assertIsInstance(uids, list)
        for uid in uids:
            member = self.us_data.get_uid(uid)[0]
            self.assertEqual(member["chamber"], "house")

    def test_locate_targets_senate_only(self):
        self.congress_campaign.campaign_subtype = "upper"
        uids = locate_targets(self.boston, self.congress_campaign, cache=self.mock_cache)
        self.assertGreaterEqual(len(uids), 1)
        for uid in uids:
            member = self.us_data.get_uid(uid)[0]
            self.assertEqual(member["chamber"], "senate")
            self.assertEqual(member["state"], "MA")


class TestCongressOrdering(BaseTestCase):
    def setUp(self):
        self.campaign_type = USCampaignType_Congress(data_provider=None)
        self.targets = {
            "upper": {
                "all": ["sen-a", "sen-b"],
                "democrats": ["sen-a"],
                "republicans": ["sen-b"],
            },
            "lower": {
                "all": ["rep-a", "rep-b"],
                "democrats": ["rep-a"],
                "republicans": ["rep-b"],
            },
        }

    def test_lower_first_order(self):
        result = self.campaign_type.sort_targets(self.targets, "both", "lower-first", shuffle_chamber=False)
        self.assertEqual(result, ["rep-a", "rep-b", "sen-a", "sen-b"])

    def test_upper_first_order(self):
        result = self.campaign_type.sort_targets(self.targets, "both", "upper-first", shuffle_chamber=False)
        self.assertEqual(result, ["sen-a", "sen-b", "rep-a", "rep-b"])

    def test_democrats_first_order(self):
        result = self.campaign_type.sort_targets(self.targets, "both", "democrats-first", shuffle_chamber=False)
        self.assertEqual(result, ["sen-a", "rep-a", "sen-b", "rep-b"])

    def test_republicans_only_order(self):
        result = self.campaign_type.sort_targets(self.targets, "both", "republicans-only", shuffle_chamber=False)
        self.assertEqual(result, ["sen-b", "rep-b"])


class TestSpecialTargetMerging(BaseTestCase):
    def setUp(self):
        self.created_campaign_ids = []
        self.created_target_ids = []

    def tearDown(self):
        if self.created_campaign_ids:
            CampaignTarget.objects.filter(campaign_id__in=self.created_campaign_ids).delete()
            Campaign.objects.filter(id__in=self.created_campaign_ids).delete()
        if self.created_target_ids:
            Target.objects.filter(id__in=self.created_target_ids).delete()
        super().tearDown()

    def make_campaign(self, include_special):
        campaign = Campaign(
            name=f"Special Merge {include_special}",
            country_code="us",
            campaign_type="congress",
            campaign_subtype="both",
            target_ordering="in-order",
            target_shuffle_chamber=False,
            campaign_state=None,
            segment_by="location",
            locate_by="postal",
            include_special=include_special,
        )
        campaign.save()
        self.created_campaign_ids.append(campaign.id)
        return campaign

    def attach_targets(self, campaign, *keys):
        for order, key in enumerate(keys):
            target = Target.objects.create(name=key.split(":")[-1], key=key)
            self.created_target_ids.append(target.id)
            CampaignTarget.objects.create(campaign=campaign, target=target, order=order)

    def fake_country_data(self, location_targets):
        class FakeCampaignType:
            def get_targets_for_campaign(self, location, campaign):
                return list(location_targets)

        class FakeCountryData:
            def get_campaign_type(self, type_id):
                return FakeCampaignType()

        return FakeCountryData()

    def test_special_before(self):
        campaign = self.make_campaign(INCLUDE_SPECIAL_BEFORE)
        self.attach_targets(campaign, "us:bioguide:SPECIAL1", "us:bioguide:SPECIAL2")
        with patch("callpower.apps.political_data.lookup.get_country_data", return_value=self.fake_country_data(["us:bioguide:LOC1"])):
            result = locate_targets("02111", campaign)
        self.assertEqual(result, ["us:bioguide:SPECIAL1", "us:bioguide:SPECIAL2", "us:bioguide:LOC1"])

    def test_special_after(self):
        campaign = self.make_campaign(INCLUDE_SPECIAL_AFTER)
        self.attach_targets(campaign, "us:bioguide:SPECIAL1", "us:bioguide:SPECIAL2")
        with patch("callpower.apps.political_data.lookup.get_country_data", return_value=self.fake_country_data(["us:bioguide:LOC1"])):
            result = locate_targets("02111", campaign)
        self.assertEqual(result, ["us:bioguide:LOC1", "us:bioguide:SPECIAL1", "us:bioguide:SPECIAL2"])

    def test_special_only(self):
        campaign = self.make_campaign(INCLUDE_SPECIAL_ONLY)
        self.attach_targets(campaign, "us:bioguide:LOC1-office", "us:bioguide:OTHER")
        with patch("callpower.apps.political_data.lookup.get_country_data", return_value=self.fake_country_data(["us:bioguide:LOC1"])):
            result = locate_targets("02111", campaign)
        self.assertEqual(result, ["us:bioguide:LOC1-office"])

    def test_special_first(self):
        campaign = self.make_campaign(INCLUDE_SPECIAL_FIRST)
        self.attach_targets(campaign, "us:bioguide:OTHER", "us:bioguide:LOC1-office")
        with patch("callpower.apps.political_data.lookup.get_country_data", return_value=self.fake_country_data(["us:bioguide:LOC1"])):
            result = locate_targets("02111", campaign)
        self.assertEqual(result, ["us:bioguide:LOC1-office", "us:bioguide:OTHER"])

    def test_special_fallback(self):
        campaign = self.make_campaign(INCLUDE_SPECIAL_FALLBACK)
        self.attach_targets(campaign, "us:bioguide:LOC1-office", "us:bioguide:OTHER")
        with patch("callpower.apps.political_data.lookup.get_country_data", return_value=self.fake_country_data(["us:bioguide:LOC1"])):
            result = locate_targets("02111", campaign)
        self.assertEqual(result, ["us:bioguide:LOC1-office"])
