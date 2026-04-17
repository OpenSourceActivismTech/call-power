from django.utils.translation import gettext_lazy as _

try:
    import represent
except ImportError:  # pragma: no cover
    represent = None

from callpower.apps.political_data.constants import CA_PROVINCE_ABBR_DICT
from callpower.apps.political_data.geocode import Geocoder, LocationError
from callpower.apps.political_data.providers.base import CampaignType, DataProvider


class CACampaignType(CampaignType):
    pass


class CACampaignType_Local(CACampaignType):
    type_name = "Local"


class CACampaignType_Custom(CACampaignType):
    type_name = "Custom"


class CACampaignType_Executive(CACampaignType):
    type_name = "Executive"
    subtypes = [("exec", _("Prime Minister")), ("office", _("Office"))]

    def all_targets(self, location, campaign_region=None):
        return {"exec": self.data_provider.get_executive()}

    def sort_targets(self, targets, subtype, order, shuffle_chamber=False):
        return list(targets.get("exec"))


class CACampaignType_Parliament(CACampaignType):
    type_name = "Parliament"
    subtypes = [("lower", _("House of Commons"))]
    target_orders = [("lower-first", _("House of Commons"))]

    def all_targets(self, location, campaign_region=None):
        return {"lower": self._get_member_of_parliament(location)}

    def sort_targets(self, targets, subtype, order, shuffle_chamber=False):
        return list(targets.get("lower")) if subtype == "lower" else []

    def _get_member_of_parliament(self, location):
        reps = self.data_provider.get_representatives(location)
        return (rep["cache_key"] for rep in reps if rep["elected_office"].upper() == "MP")


class CACampaignType_Province(CACampaignType):
    type_name = "Province"
    subtypes = [("lower", _("Legislature"))]
    target_orders = [("lower-first", _("Legislature"))]
    provincial_legislatures = {
        "AB": {"body": "alberta-legislature", "office": "MLA"},
        "BC": {"body": "bc-legislature", "office": "MLA"},
        "MB": {"body": "manitoba-legislature", "office": "MLA"},
        "NB": {"body": "new-brunswick-legislature", "office": "MLA"},
        "NL": {"body": "newfoundland-labrador-legislature", "office": "MHA"},
        "NS": {"body": "nova-scotia-legislature", "office": "MLA"},
        "ON": {"body": "ontario-legislature", "office": "MPP"},
        "PE": {"body": "pei-legislature", "office": "MLA"},
        "QC": {"body": "quebec-assemblee-nationale", "office": "MNA"},
        "SK": {"body": "saskatchewan-legislature", "office": "MLA"},
    }

    @property
    def region_choices(self):
        return {"": "", **{abbr: CA_PROVINCE_ABBR_DICT.get(abbr) for abbr in self.provincial_legislatures}}

    def all_targets(self, location, campaign_region=None):
        return {"lower": self._get_province_representative(location, campaign_region)}

    def sort_targets(self, targets, subtype, order, shuffle_chamber=False):
        return list(targets.get("lower")) if subtype == "lower" else []

    def _get_province_representative(self, location, campaign_region=None):
        legislature = self.provincial_legislatures.get(campaign_region)
        if not legislature:
            return []
        reps = self.data_provider.get_representatives(location, legislature["body"])
        return (rep["cache_key"] for rep in reps if rep["elected_office"].upper() == legislature["office"])


class CADataProvider(DataProvider):
    country_name = "Canada"
    country_code = "ca"
    campaign_types = [
        ("executive", CACampaignType_Executive),
        ("parliament", CACampaignType_Parliament),
        ("province", CACampaignType_Province),
        ("local", CACampaignType_Local),
        ("custom", CACampaignType_Custom),
    ]
    KEY_OPENNORTH = "ca:opennorth:{boundary}"

    def __init__(self, cache, **kwargs):
        super().__init__(cache, **kwargs)
        self._geocoder = Geocoder(country="CA")

    def get_location(self, locate_by, raw):
        if locate_by == "postal":
            return self._geocoder.postal(raw)
        if locate_by == "address":
            return self._geocoder.geocode(raw)
        if locate_by == "latlon":
            return self._geocoder.reverse(raw)
        return None

    def load_data(self):
        self.cache_set("political_data:ca", ["data sourced from represent.opennorth.ca"])
        return 0

    def get_executive(self):
        return [{"office": "Prime Minister's Office", "number": "16139924211"}]

    def boundary_url_to_key(self, related_url):
        boundary = related_url.strip("/").replace("boundaries/", "")
        return boundary.replace("/", ":")

    def get_representatives(self, location, body_name="house-of-commons"):
        if represent is None:
            raise LocationError("represent is not installed")
        if not location or not (location.latitude and location.longitude):
            raise LocationError("CADataProvider.get_representatives requires location with lat/lon")
        point = f"{location.latitude},{location.longitude}"
        reps = represent.representative(point=point, repr_set=body_name)
        keys = []
        for rep in reps:
            boundary_key = self.boundary_url_to_key(rep["related"]["boundary_url"])
            cache_key = self.KEY_OPENNORTH.format(boundary=boundary_key)
            rep["boundary_key"] = boundary_key
            rep["cache_key"] = cache_key
            self.cache_set(cache_key, rep)
            keys.append(rep)
        return keys
