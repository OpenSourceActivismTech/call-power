import werkzeug.contrib.cache
from flask_babel import gettext as _
from graphqlclient import GraphQLClient

from . import DataProvider, CampaignType

from ..adapters import OpenStatesData
from ..geocode import Geocoder, LocationError
from ..constants import US_STATES
from ...campaign.constants import (LOCATION_POSTAL, LOCATION_ADDRESS, LOCATION_LATLON)
from ...utils import ocd_field

import os
import random
import csv
import yaml
import json
import collections
from datetime import datetime
import logging
log = logging.getLogger(__name__)

try:
    from yaml import CLoader as yamlLoader
except ImportError:
    log.info('install libyaml to speed up loadpoliticaldata')
    from yaml import Loader as yamlLoader

class USCampaignType(CampaignType):
    pass


class USCampaignType_Local(USCampaignType):
    type_name = "Local"


class USCampaignType_Custom(USCampaignType):
    type_name = "Custom"


class USCampaignType_Executive(USCampaignType):
    type_name = "Executive"

    subtypes = [
        ('exec', _("President")),
        ('office', _("Office"))
    ]

    def all_targets(self, location, campaign_region=None):
        return {
            'exec': self._get_executive()
        }

    def _get_executive(self):
        return self.data_provider.get_executive()


class USCampaignType_Congress(USCampaignType):
    type_name = "Congress"

    subtypes = [
        ('both', _("Both Bodies")),
        ('upper', _("Senate")),
        ('lower', _("House"))
    ]
    target_orders = [
        ('shuffle', _("Shuffle")),
        ('upper-first', _("Senate First")),
        ('lower-first', _("House First")),
        ('democrats-first', _("Democrats First")),
        ('republicans-first', _("Republicans First")),
    ]

    @property
    def region_choices(self):
        return US_STATES

    def all_targets(self, location, campaign_region=None):
        return {
            'upper': self._get_senators(location),
            'lower': self._get_representative(location),
            'republicans': self._get_congress_party(location, 'Republican'),
            'democrats': self._get_congress_party(location, 'Democrat'),
        }

    def sort_targets(self, targets, subtype, order, shuffle_chamber=True):
        upper_targets = list(targets.get('upper'))
        lower_targets = list(targets.get('lower'))
        republican_targets = list(targets.get('republicans'))
        democrat_targets = list(targets.get('democrats'))

        # by default, shuffle target ordering within chamber
        if shuffle_chamber:
            random.shuffle(upper_targets)
            random.shuffle(lower_targets)

        if subtype == 'both':
            if order == 'upper-first':
                return upper_targets + lower_targets
            elif order == 'democrats-first':
                return democrat_targets + republican_targets
            elif order == 'republicans-first':
                return republican_targets + democrat_targets
            else:
                return lower_targets + upper_targets
        elif subtype == 'upper':
            return upper_targets
        elif subtype == 'lower':
            return lower_targets
        elif subtype == 'exec':
            return exec_targets

    def _get_senators(self, location):
        districts = self.data_provider.get_districts(location.postal)
        # This is a set because zipcodes may cross states
        states = set(d['state'] for d in districts)

        for state in states:
            for senator in self.data_provider.get_senators(state):
                yield self.data_provider.KEY_BIOGUIDE.format(**senator)

    def _get_representative(self, location):
        districts = self.data_provider.get_districts(location.postal)

        for district in districts:
            rep = self.data_provider.get_house_members(district['state'], district['house_district'])
            if rep:
                yield self.data_provider.KEY_BIOGUIDE.format(**rep[0])

    def _get_congress_party(self, location, party):
        districts = self.data_provider.get_districts(location.postal)
        # This is a set because zipcodes may cross states
        states = set(d['state'] for d in districts)

        matched_party = []

        for state in states:
            for senator in self.data_provider.get_senators(state):
                if senator.get('party') == party:
                    matched_party.append(self.data_provider.KEY_BIOGUIDE.format(**senator))

        for district in districts:
            rep = self.data_provider.get_house_members(district['state'], district['house_district'])
            if rep and rep[0].get('party') == party:
                matched_party.append(self.data_provider.KEY_BIOGUIDE.format(**rep[0]))
        return matched_party


class USCampaignType_State(USCampaignType):
    type_name = "State"

    subtypes = [
        ('exec', _("Governor")),
        ('both', _("Legislature - Both Bodies")),
        ('upper', _("Legislature - Upper Body")),
        ('lower', _("Legislature - Lower Body"))
    ]
    target_orders = [
        ('shuffle', _("Shuffle")),
        ('upper-first', _("Upper First")),
        ('lower-first', _("Lower First"))
    ]

    @property
    def region_choices(self):
        return US_STATES

    def get_subtype_display(self, subtype, campaign_region=None):
        display = super(USCampaignType_State, self).get_subtype_display(subtype, campaign_region)
        if display:
            return u'{} - {}'.format(campaign_region, display)
        else:
            return display

    def all_targets(self, location, campaign_region=None):
        UPPER = 'upper'
        LOWER = 'lower'

        if location.state == 'NE':
            # unicameral, so there's only "legislature"
            UPPER = None
            LOWER = 'legislature'

        return {
            'exec': self._get_state_governor(location, campaign_region),
            'upper': self._get_state_legislators(location, campaign_region, UPPER),
            'lower': self._get_state_legislators(location, campaign_region, LOWER)
        }

    def sort_targets(self, targets, subtype, order, shuffle_chamber=True):
        upper_targets = list(targets.get('upper'))
        lower_targets = list(targets.get('lower'))
        exec_targets = list(targets.get('exec'))

        # by default, shuffle target ordering within chamber
        if shuffle_chamber:
            random.shuffle(upper_targets)
            random.shuffle(lower_targets)

        if subtype == 'both':
            if order == 'upper-first':
                return upper_targets + lower_targets
            else:
                return lower_targets + upper_targets
        elif subtype == 'upper':
            return upper_targets
        elif subtype == 'lower':
            return lower_targets
        elif subtype == 'exec':
            return exec_targets

    def _get_state_governor(self, location, campaign_region=None):
        return [self.data_provider.KEY_GOVERNOR.format(state=location.state)]

    def _get_state_legislators(self, location, campaign_region=None, chamber_name='upper'):
        legislators = self.data_provider.get_state_legislators(location)
        filtered = self._filter_legislators(legislators, campaign_region)
        return (l['cache_key'] for l in filtered if l['chamber'] == chamber_name)

    def _filter_legislators(self, legislators, campaign_region=None):
        for legislator in legislators:
            in_state = campaign_region is None or legislator['state'].upper() == campaign_region.upper()
            if in_state:
                yield legislator


class USDataProvider(DataProvider):
    country_name = "United States"
    country_code = "us"

    campaign_types = [
        ('executive', USCampaignType_Executive),
        ('congress', USCampaignType_Congress),
        ('state', USCampaignType_State),
        ('local', USCampaignType_Local),
        ('custom', USCampaignType_Custom)
    ]

    KEY_BIOGUIDE = 'us:bioguide:{bioguide_id}'
    KEY_HOUSE = 'us:house:{state}:{district}'
    KEY_SENATE = 'us:senate:{state}'
    KEY_OPENSTATES = 'us_state:openstates:{id}'
    KEY_GOVERNOR = 'us_state:governor:{state}'
    KEY_ZIPCODE = 'us:zipcode:{zipcode}'

    SORTED_SETS = ['us:house', 'us:senate', 'us_state:governor']

    def __init__(self, cache, api_cache=None, **kwargs):
        super(USDataProvider, self).__init__(**kwargs)
        self._cache = cache
        self._geocoder = Geocoder(country='US')
        self._openstates = GraphQLClient('https://openstates.org/graphql')
        self._openstates.inject_token(os.environ.get('OPENSTATES_API_KEY'), 'x-api-key')

    def get_location(self, locate_by, raw, ignore_local_cache=False):
        if locate_by == LOCATION_POSTAL:
            if ignore_local_cache:
                if type(raw) == dict:
                    return self._geocoder.postal(raw.get('zipcode'), provider=None)
                else:
                    return self._geocoder.postal(raw, provider=None)
            else:
                return self._geocoder.postal(raw, provider=self)
        elif locate_by == LOCATION_ADDRESS:
            return self._geocoder.geocode(raw)
        elif locate_by == LOCATION_LATLON:
            return self._geocoder.reverse(raw)
        else:
            return None

    def _load_legislators(self):
        """
        Load US legislator data from us_congress_current.yaml
        Merges with district office data from us_congress_offices.yaml by bioguide id
        Returns a dictionary keyed by state, district and bioguide id

        eg us:senate:CA = [{'title':'Sen', 'first_name':'Dianne',  'last_name': 'Feinstein', ...},
                           {'title':'Sen', 'first_name':'Barbara', 'last_name': 'Boxer', ...}]
        or us:house:CA:13 = [{'title':'Rep', 'first_name':'Barbara',  'last_name': 'Lee', ...}]
        or us:bioguide:F000062 = [{'title':'Sen', 'first_name':'Dianne',  'last_name': 'Feinstein', ...}]
        """
        legislators = collections.defaultdict(list)
        offices = collections.defaultdict(list)

        with open('call_server/political_data/data/us_congress_current.yaml') as f1, \
            open('call_server/political_data/data/us_congress_historical.yaml') as f2, \
            open('call_server/political_data/data/us_congress_offices.yaml') as f3:

            current_leg = yaml.load(f1, Loader=yamlLoader)
            historical_leg = yaml.load(f2, Loader=yamlLoader)
            office_info = yaml.load(f3, Loader=yamlLoader)

            for info in office_info:
                id = info['id']['bioguide']
                offices[id] = info.get('offices', [])

            for info in current_leg+historical_leg:
                term = info['terms'][-1]
                if term['start'] < "2015-01-01":
                    continue # skip loading historical data
                    # set this to be before the start date of the oldest currently seated Senate class

                term['current'] = (term['end'] >= datetime.now().strftime('%Y-%m-%d'))

                if term.get('phone') is None:
                    term['name'] = info['name']['last']
                    if term['current']:
                        # try to pull from previous term, for re-elected incumbents
                        try:
                            prev_term = info['terms'][-2]
                            old_phone = prev_term.get('phone')
                            if old_phone and prev_term['type'] == term['type']:
                                term['phone'] = old_phone
                                log.info(u"pulling phone number from previous {type} term for {name}".format(**term))
                            else:
                                log.warning(u"term {start} - {end} does not have field phone for {type} {name}".format(**term))
                        except IndexError:
                            log.warning(u"term {start} - {end} does not have field phone for {type} {name}".format(**term))
                    else:
                        continue

                district = str(term['district']) if term.has_key('district') else None

                record = {
                    'first_name':  info['name']['first'],
                    'last_name':   info['name']['last'],
                    'bioguide_id': info['id']['bioguide'],
                    'title':       "Senator" if term['type'] == "sen" else "Representative",
                    'phone':       term.get('phone'),
                    'chamber':     "senate" if term['type'] == "sen" else "house",
                    'state':       term['state'],
                    'district':    district,
                    'offices':     offices.get(info['id']['bioguide'], []),
                    'current':     term['current'],
                    'party':       term['party'],
                }

                direct_key = self.KEY_BIOGUIDE.format(**record)
                if record['chamber'] == "senate":
                    chamber_key = self.KEY_SENATE.format(**record)
                else:
                    chamber_key = self.KEY_HOUSE.format(**record)

                # we want bioguide access to all recent legislators
                legislators[direct_key].append(record)
                # but only house or senate access to current ones
                if term['current']:
                    legislators[chamber_key].append(record)

        return legislators


    def _load_districts(self):
        """
        Load US congressional district data from saved file
        Returns a list of dictionaries keyed by zipcode to cache for fast lookup

        eg us:zipcode:94612 = [{'state':'CA', 'house_district': 13}]
        or us:zipcode:54409 = [{'state':'WI', 'house_district': 7}, {'state':'WI', 'house_district': 8}]
        """
        districts = collections.defaultdict(list)

        with open('call_server/political_data/data/us_districts.csv') as f:
            reader = csv.DictReader(f)

            for row in reader:
                d = {
                    'state': row['state_abbr'],
                    'zipcode': row['zcta'],
                    'house_district': row['cd']
                }
                cache_key = self.KEY_ZIPCODE.format(**d)
                districts[cache_key].append(d)

        return districts

    def _load_governors(self):
        """
        Load US state governor data from saved file
        Returns a dictionary keyed by state to cache for fast lookup

        eg us_state:governor:CA = [{'title':'Governor', 'name':'Jerry Brown Jr.', 'phone': '18008076755', 'state': 'CA', 'state_name': 'California'}]
        """
        governors = collections.defaultdict(list)

        with open('call_server/political_data/data/us_governors.csv') as f:
            reader = csv.DictReader(f)

            for l in reader:
                direct_key = self.KEY_GOVERNOR.format(state=l['state_abbr'])
                d = {
                    'title': 'Governor',
                    'first_name': l.get('first_name'),
                    'last_name': l.get('last_name'),
                    'phone': l.get('phone'),
                    'state': l.get('state_abbr'),
                    'state_name': l.get('state_name')
                }
                governors[direct_key] = [d, ]
        return governors

    def load_data(self):
        districts = self._load_districts()
        legislators = self._load_legislators()
        governors = self._load_governors()

        self.cache_set_many(districts)
        self.cache_set_many(legislators)
        self.cache_set_many(governors)

        # if cache is redis, add lexigraphical index on states, names
        if hasattr(self._cache, 'cache') and isinstance(self._cache.cache, werkzeug.contrib.cache.RedisCache):
            redis = self._cache.cache._client
            searchable_items = legislators.items() + governors.items()
            for (key,record) in searchable_items:
                for sorted_key in self.SORTED_SETS:
                    if key.startswith(sorted_key):
                        redis.zadd(sorted_key, key, 0)

        success = [
            "%s zipcodes" % len(districts),
            "%s legislators" % len(legislators),
            "%s governors" % len(governors),
            "at %s" % datetime.now(),
        ]
        log.info('loaded %s' % ', '.join(success))
        self.cache_set('political_data:us', success)

        return len(districts) + len(legislators) + len(governors)


    # convenience methods for easy house, senate, district access
    def get_executive(self):
        # Whitehouse comment line is disconnected
        # return [{'office': 'Whitehouse Comment Line',
        #        'number': '12024561111'}]
        return [{'office': 'Whitehouse Switchboard',
                'number': '12024561414'}]

    def get_house_members(self, state, district):
        key = self.KEY_HOUSE.format(state=state, district=district)
        return self.cache_get(key)

    def get_senators(self, state):
        key = self.KEY_SENATE.format(state=state)
        return self.cache_get(key)

    def get_districts(self, zipcode):
        key = self.KEY_ZIPCODE.format(zipcode=zipcode)
        return self.cache_get(key)

    def get_state_governor(self, state):
        key = self.KEY_GOVERNOR.format(state=state)
        return self.cache_get(key)

    def get_state_legislators(self, location):
        if not (location.latitude and location.longitude):
            location = self.get_location(LOCATION_POSTAL, location.raw, ignore_local_cache=True)
        
        if not (location.latitude and location.longitude):
            raise LocationError('USDataProvider.get_state_legislators requires location with lat/lon')    

        # execute GraphQL query to get id, name, chamber, and contactDetails
        api_response = self._openstates.execute('''
            { people(latitude: %f, longitude: %f, first: 100) {
                edges {
                  node {
                    id
                    name
                    givenName
                    familyName
                    chamber: currentMemberships(classification:["upper", "lower", "legislature"]) {
                      post {
                        label
                        role
                        division {
                          id
                        }
                      }
                      organization {
                        name
                        classification
                      }
                    }
                    contactDetails {
                        value
                        note
                        type
                    }
                  }
                }
              }
            }''' % (location.latitude, location.longitude))
        parsed_response = json.loads(api_response)

        legislators = []
        # save results individually in local cache
        for edge in parsed_response['data']['people']['edges']:
            leg = edge['node']

            chamber_classification = leg['chamber'][0]['organization']['classification']
            district_label = leg['chamber'][0]['post']['label']
            post_division = leg['chamber'][0]['post']['division']['id']
            post_state = ocd_field(post_division, 'state').upper()
            role_title = leg['chamber'][0]['post']['role']

            leg['chamber'] = chamber_classification
            leg['state'] = post_state
            leg['district'] = district_label
            leg['title'] = role_title

            key = self.KEY_OPENSTATES.format(id=leg['id'])
            leg['cache_key'] = key
            self.cache_set(key, leg)
            legislators.append(leg)

        return legislators

    def get_bioguide(self, bioguide):
        # try first to get from cache
        key = self.KEY_BIOGUIDE.format(bioguide_id=bioguide)
        return self.cache_get(key, list({}))

    def get_state_legid(self, ocd_id):
        # try first to get from cache
        key = self.KEY_OPENSTATES.format(id=ocd_id)
        leg = self.cache_get(key, None)
        
        if not leg:
            # or lookup from openstates and save
            api_response = self._openstates.execute('''{
                person(id:"%s") {
                  id
                  name
                  givenName
                  familyName
                  chamber: currentMemberships(classification:["upper", "lower", "legislature"]) {
                      post {
                        label
                        role
                        division {
                          id
                        }
                      }
                      organization {
                        name
                        classification
                      }
                  }
                  contactDetails {
                    value
                    note
                    type
                  }
                }
                }''' % ocd_id)
            parsed_response = json.loads(api_response)
            leg = parsed_response['data']['person']

            chamber_classification = leg['chamber'][0]['organization']['classification']
            district_label = leg['chamber'][0]['post']['label']
            post_division = leg['chamber'][0]['post']['division']['id']
            post_state = ocd_field(post_division, 'state').upper()
            role_title = leg['chamber'][0]['post']['role']

            leg['chamber'] = chamber_classification
            leg['state'] = post_state
            leg['district'] = district_label
            leg['title'] = role_title

            leg['cache_key'] = key
            self.cache_set(key, leg)
        return leg

    def search_state_leg(self, state, chamber, name):
        # first get the legislature chamber OCD ID
        organization_response = self._openstates.execute('''
            query getOrganizationID($stateOCD:String, $chamber:String) {
              jurisdiction(id: $stateOCD) {
                organizations(classification: [$chamber], first: 3) {
                  edges {
                    node {
                      id
                    }
                  }
                }
              }
            }
        ''',{
            'stateOCD': 'ocd-jurisdiction/country:us/state:%s/government' % state.lower(),
            'chamber': chamber
        })
        organization_parsed = json.loads(organization_response)
        org_ocd_id = organization_parsed['data']['jurisdiction']['organizations']['edges'][0]['node']['id']

        # now use that to query for members by name
        person_response = self._openstates.execute('''
            query getLegislatorContact($name: String, $organizationID: String, $chamber: String) {
              people(name: $name, memberOf: $organizationID, first: 5) {
                edges {
                  node {
                    currentMemberships(classification: [$chamber]) {
                      id
                      post {
                        label
                        role
                        division {
                          id
                        }
                      }
                    }
                    id
                    name
                    contactDetails {
                      type
                      value
                      note
                      label
                    }
                  }
                }
              }
            }
        ''',{
            'organizationID': org_ocd_id,
            'chamber': chamber,
            'name': name
        })
        people_parsed = json.loads(person_response)
        result_data = []
        for person_edge in people_parsed['data']['people']['edges']:
            person = person_edge['node']
            person['chamber'] = chamber
            person['district'] = person['currentMemberships'][0]['post']['label']
            adapter = OpenStatesData()
            target = adapter.target(person)
            target['phone'] = target.pop('number') # fix field name inconsistency...
            result_data.append(target)
        return result_data

    def get_uid(self, uid):
        return self.cache_get(uid, dict())
