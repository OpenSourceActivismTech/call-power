import collections
import csv
import json
import os
import random
from datetime import datetime
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from graphqlclient import GraphQLClient
import yaml

from callpower.apps.political_data.constants import US_STATES
from callpower.apps.political_data.geocode import Geocoder, LocationError
from callpower.apps.political_data.providers.base import CampaignType, DataProvider


DATA_DIR = Path(__file__).resolve().parents[5] / "call_server" / "political_data" / "data"


def ocd_field(ocd_data, field):
    for part in ocd_data.split("/"):
        if ":" in part:
            label, value = part.split(":")
            if label == field:
                return value
    return ""


class USCampaignType(CampaignType):
    pass


class USCampaignType_Local(USCampaignType):
    type_name = "Local"


class USCampaignType_Custom(USCampaignType):
    type_name = "Custom"


class USCampaignType_Executive(USCampaignType):
    type_name = "Executive"
    subtypes = [("exec", _("President")), ("office", _("Office"))]

    def all_targets(self, location, campaign_region=None):
        return {"exec": self.data_provider.get_executive()}

    def sort_targets(self, targets, subtype, order, shuffle_chamber=True):
        return list(targets.get("exec"))


class USCampaignType_Congress(USCampaignType):
    type_name = "Congress"
    subtypes = [("both", _("Both Bodies")), ("upper", _("Senate")), ("lower", _("House"))]
    target_orders = [
        ("shuffle", _("Shuffle")),
        ("upper-first", _("Senate First")),
        ("lower-first", _("House First")),
        ("democrats-first", _("Democrats First")),
        ("republicans-first", _("Republicans First")),
        ("democrats-only", _("Democrats Only")),
        ("republicans-only", _("Republicans Only")),
    ]

    @property
    def region_choices(self):
        return US_STATES

    def all_targets(self, location, campaign_region=None):
        return {
            "upper": {
                "all": self._get_senators(location),
                "democrats": self._get_senate_party(location, "Democrat"),
                "republicans": self._get_senate_party(location, "Republican"),
            },
            "lower": {
                "all": self._get_representative(location),
                "democrats": self._get_congress_party(location, "Democrat"),
                "republicans": self._get_congress_party(location, "Republican"),
            },
        }

    def sort_targets(self, targets, subtype, order, shuffle_chamber=True):
        upper_targets = list(targets.get("upper").get("all"))
        lower_targets = list(targets.get("lower").get("all"))
        democrats_upper = list(targets.get("upper").get("democrats"))
        republicans_upper = list(targets.get("upper").get("republicans"))
        democrats_lower = list(targets.get("lower").get("democrats"))
        republicans_lower = list(targets.get("lower").get("republicans"))
        democrat_targets = democrats_upper + democrats_lower
        republican_targets = republicans_upper + republicans_lower

        if shuffle_chamber:
            random.shuffle(upper_targets)
            random.shuffle(lower_targets)

        if subtype == "both":
            if order == "upper-first":
                return upper_targets + lower_targets
            if order == "democrats-first":
                return democrat_targets + republican_targets
            if order == "republicans-first":
                return republican_targets + democrat_targets
            if order == "democrats-only":
                return democrat_targets
            if order == "republicans-only":
                return republican_targets
            return lower_targets + upper_targets
        if subtype == "upper":
            if order == "democrats-first":
                return democrats_upper + republicans_upper
            if order == "republicans-first":
                return republicans_upper + democrats_upper
            if order == "democrats-only":
                return democrats_upper
            if order == "republicans-only":
                return republicans_upper
            return upper_targets
        if subtype == "lower":
            return lower_targets
        return []

    def _get_senators(self, location):
        districts = self.data_provider.get_districts(location.postal)
        states = set(d["state"] for d in districts)
        for state in states:
            for senator in self.data_provider.get_senators(state):
                yield self.data_provider.KEY_BIOGUIDE.format(**senator)

    def _get_representative(self, location):
        for district in self.data_provider.get_districts(location.postal):
            rep = self.data_provider.get_house_members(district["state"], district["house_district"])
            if rep:
                yield self.data_provider.KEY_BIOGUIDE.format(**rep[0])

    def _get_senate_party(self, location, party):
        matched = []
        districts = self.data_provider.get_districts(location.postal)
        states = set(d["state"] for d in districts)
        for state in states:
            for senator in self.data_provider.get_senators(state):
                if senator.get("party") == party:
                    matched.append(self.data_provider.KEY_BIOGUIDE.format(**senator))
        return matched

    def _get_congress_party(self, location, party):
        matched = []
        for district in self.data_provider.get_districts(location.postal):
            rep = self.data_provider.get_house_members(district["state"], district["house_district"])
            if rep and rep[0].get("party") == party:
                matched.append(self.data_provider.KEY_BIOGUIDE.format(**rep[0]))
        return matched


class USCampaignType_State(USCampaignType):
    type_name = "State"
    subtypes = [
        ("exec", _("Governor")),
        ("both", _("Legislature - Both Bodies")),
        ("upper", _("Legislature - Upper Body")),
        ("lower", _("Legislature - Lower Body")),
    ]
    target_orders = [
        ("shuffle", _("Shuffle")),
        ("upper-first", _("Upper First")),
        ("lower-first", _("Lower First")),
    ]

    @property
    def region_choices(self):
        return US_STATES

    def all_targets(self, location, campaign_region=None):
        upper = "upper"
        lower = "lower"
        if location.state == "NE":
            upper = None
            lower = "legislature"
        return {
            "exec": self._get_state_governor(location, campaign_region),
            "upper": self._get_state_legislators(location, campaign_region, upper),
            "lower": self._get_state_legislators(location, campaign_region, lower),
        }

    def sort_targets(self, targets, subtype, order, shuffle_chamber=True):
        upper_targets = list(targets.get("upper"))
        lower_targets = list(targets.get("lower"))
        exec_targets = list(targets.get("exec"))
        if shuffle_chamber:
            random.shuffle(upper_targets)
            random.shuffle(lower_targets)
        if subtype == "both":
            return upper_targets + lower_targets if order == "upper-first" else lower_targets + upper_targets
        if subtype == "upper":
            return upper_targets
        if subtype == "lower":
            return lower_targets
        if subtype == "exec":
            return exec_targets
        return []

    def _get_state_governor(self, location, campaign_region=None):
        return [self.data_provider.KEY_GOVERNOR.format(state=location.state)]

    def _get_state_legislators(self, location, campaign_region=None, chamber_name="upper"):
        legislators = self.data_provider.get_state_legislators(location)
        return (
            legislator["cache_key"]
            for legislator in legislators
            if legislator["chamber"] == chamber_name
            and (campaign_region is None or legislator["state"].upper() == campaign_region.upper())
        )


class USDataProvider(DataProvider):
    country_name = "United States"
    country_code = "us"
    campaign_types = [
        ("executive", USCampaignType_Executive),
        ("congress", USCampaignType_Congress),
        ("state", USCampaignType_State),
        ("local", USCampaignType_Local),
        ("custom", USCampaignType_Custom),
    ]

    KEY_BIOGUIDE = "us:bioguide:{bioguide_id}"
    KEY_HOUSE = "us:house:{state}:{district}"
    KEY_SENATE = "us:senate:{state}"
    KEY_OPENSTATES = "us_state:openstates:{id}"
    KEY_GOVERNOR = "us_state:governor:{state}"
    KEY_ZIPCODE = "us:zipcode:{zipcode}"

    def __init__(self, cache, **kwargs):
        super().__init__(cache, **kwargs)
        self._geocoder = Geocoder(country="US")
        self._openstates = GraphQLClient("https://openstates.org/graphql")
        api_key = os.environ.get("OPENSTATES_API_KEY")
        if api_key:
            self._openstates.inject_token(api_key, "x-api-key")

    def get_location(self, locate_by, raw, ignore_local_cache=False):
        if locate_by == "postal":
            return self._geocoder.postal(raw, provider=None if ignore_local_cache else self)
        if locate_by == "address":
            return self._geocoder.geocode(raw)
        if locate_by == "latlon":
            return self._geocoder.reverse(raw)
        return None

    def _load_districts(self):
        districts = collections.defaultdict(list)
        with open(DATA_DIR / "us_districts.csv") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                record = {
                    "state": row["state_abbr"],
                    "zipcode": row["zcta"],
                    "house_district": row["cd"],
                }
                districts[self.KEY_ZIPCODE.format(**record)].append(record)
        return districts

    def _load_governors(self):
        governors = collections.defaultdict(list)
        with open(DATA_DIR / "us_governors.csv") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = self.KEY_GOVERNOR.format(state=row["state_abbr"])
                governors[key] = [{
                    "title": "Governor",
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "phone": row.get("phone"),
                    "state": row.get("state_abbr"),
                    "state_name": row.get("state_name"),
                }]
        return governors

    def _load_legislators(self):
        legislators = collections.defaultdict(list)
        offices = collections.defaultdict(list)
        with open(DATA_DIR / "us_congress_current.yaml") as current_handle, \
            open(DATA_DIR / "us_congress_historical.yaml") as historical_handle, \
            open(DATA_DIR / "us_congress_offices.yaml") as offices_handle:
            current_leg = yaml.safe_load(current_handle)
            historical_leg = yaml.safe_load(historical_handle)
            office_info = yaml.safe_load(offices_handle)

        for info in office_info:
            bioguide_id = info["id"]["bioguide"]
            offices[bioguide_id] = info.get("offices", [])

        for info in current_leg + historical_leg:
            term = info["terms"][-1]
            if term["start"] < "2015-01-01":
                continue
            term["current"] = term["end"] >= datetime.now().strftime("%Y-%m-%d")
            if term.get("phone") is None and not term["current"]:
                continue
            district = str(term["district"]) if "district" in term else None
            bioguide = info.get("id", {}).get("bioguide", "")
            record = {
                "first_name": info["name"]["first"],
                "last_name": info["name"]["last"],
                "bioguide_id": bioguide,
                "title": "Senator" if term["type"] == "sen" else "Representative",
                "phone": term.get("phone"),
                "chamber": "senate" if term["type"] == "sen" else "house",
                "state": term["state"],
                "district": district,
                "offices": offices.get(bioguide, []),
                "current": term["current"],
                "party": term.get("caucus") or term.get("party"),
            }
            if info["name"].get("nickname"):
                record["nick_name"] = info["name"]["nickname"]
            direct_key = self.KEY_BIOGUIDE.format(**record)
            chamber_key = self.KEY_SENATE.format(**record) if record["chamber"] == "senate" else self.KEY_HOUSE.format(**record)
            legislators[direct_key].append(record)
            if term["current"]:
                legislators[chamber_key].append(record)
        return legislators

    def load_data(self):
        districts = self._load_districts()
        legislators = self._load_legislators()
        governors = self._load_governors()
        self.cache_set_many(districts)
        self.cache_set_many(legislators)
        self.cache_set_many(governors)
        self.cache_set("political_data:us", [
            f"{len(districts)} zipcodes",
            f"{len(legislators)} legislators",
            f"{len(governors)} governors",
        ])
        return len(districts) + len(legislators) + len(governors)

    def get_executive(self):
        return [{"office": "Whitehouse Switchboard", "number": "12024561414"}]

    def get_house_members(self, state, district):
        return self.cache_get(self.KEY_HOUSE.format(state=state, district=district), [])

    def get_senators(self, state):
        return self.cache_get(self.KEY_SENATE.format(state=state), [])

    def get_districts(self, zipcode):
        return self.cache_get(self.KEY_ZIPCODE.format(zipcode=zipcode), [])

    def get_state_governor(self, state):
        return self.cache_get(self.KEY_GOVERNOR.format(state=state), [])

    def get_uid(self, uid):
        return self.cache_get(uid, {})

    def get_state_legislators(self, location):
        if not (location.latitude and location.longitude):
            location = self.get_location("postal", location.raw, ignore_local_cache=True)
        if not (location.latitude and location.longitude):
            raise LocationError("USDataProvider.get_state_legislators requires location with lat/lon")
        api_response = self._openstates.execute(
            """
            { people(latitude: %f, longitude: %f, first: 100) {
                edges {
                  node {
                    id
                    name
                    givenName
                    familyName
                    chamber: currentMemberships(classification:["upper", "lower", "legislature"]) {
                      post { label role division { id } }
                      organization { name classification jurisdictionId }
                    }
                    contactDetails { value note type }
                  }
                }
              }
            }"""
            % (location.latitude, location.longitude)
        )
        parsed = json.loads(api_response)
        legislators = []
        for edge in parsed["data"]["people"]["edges"]:
            legislator = edge["node"]
            legislator["chamber"] = legislator["chamber"][0]["organization"]["classification"]
            legislator["district"] = legislator["chamber"][0]["post"]["label"]
            division = legislator["chamber"][0]["post"]["division"]["id"]
            legislator["state"] = ocd_field(division, "state").upper()
            legislator["title"] = legislator["chamber"][0]["post"]["role"]
            if not ocd_field(legislator["chamber"][0]["organization"]["jurisdictionId"], "state"):
                continue
            key = self.KEY_OPENSTATES.format(id=legislator["id"])
            legislator["cache_key"] = key
            self.cache_set(key, legislator)
            legislators.append(legislator)
        return legislators

    def get_state_legid(self, ocd_id):
        key = self.KEY_OPENSTATES.format(id=ocd_id)
        legislator = self.cache_get(key)
        if legislator:
            return legislator
        api_response = self._openstates.execute(
            """{
                person(id:"%s") {
                  id
                  name
                  givenName
                  familyName
                  chamber: currentMemberships(classification:["upper", "lower", "legislature"]) {
                      post { label role division { id } }
                      organization { name classification }
                  }
                  contactDetails { value note type }
                }
            }"""
            % ocd_id
        )
        legislator = json.loads(api_response)["data"]["person"]
        legislator["chamber"] = legislator["chamber"][0]["organization"]["classification"]
        legislator["district"] = legislator["chamber"][0]["post"]["label"]
        division = legislator["chamber"][0]["post"]["division"]["id"]
        legislator["state"] = ocd_field(division, "state").upper()
        legislator["title"] = legislator["chamber"][0]["post"]["role"]
        legislator["cache_key"] = key
        self.cache_set(key, legislator)
        return legislator
