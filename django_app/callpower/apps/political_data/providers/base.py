from django.utils.translation import gettext_lazy as _


class DataProvider:
    country_name = None
    campaign_types = []

    def __init__(self, cache, **kwargs):
        self._cache = cache

    @property
    def campaign_type_choices(self):
        return [(key, campaign_type.type_name) for key, campaign_type in self.campaign_types]

    def get_campaign_type(self, type_id):
        type_class = dict(self.campaign_types).get(type_id)
        return type_class(self)

    def cache_get(self, key, default=None):
        return self._cache.get(key, default)

    def cache_set(self, key, value):
        self._cache.set(key, value)

    def cache_set_many(self, mapping):
        self._cache.set_many(mapping)

    def cache_search(self, prefix):
        return self._cache.search_prefix(prefix)


class CampaignType:
    type_name = None
    subtypes = []
    target_orders = [
        ("in-order", _("In order")),
        ("shuffle", _("Shuffle")),
    ]

    def __init__(self, data_provider):
        self.data_provider = data_provider

    @property
    def region_choices(self):
        return []

    @property
    def subtype_choices(self):
        return CampaignType.subtypes + self.subtypes

    @property
    def target_order_choices(self):
        return CampaignType.target_orders + self.target_orders

    def get_targets_for_campaign(self, location, campaign):
        if isinstance(location, str):
            location = self.data_provider.get_location(campaign.locate_by, location)
        all_targets = self.all_targets(location, campaign.campaign_state)
        return self.sort_targets(
            all_targets,
            campaign.campaign_subtype,
            campaign.target_ordering,
            shuffle_chamber=campaign.target_shuffle_chamber,
        )
