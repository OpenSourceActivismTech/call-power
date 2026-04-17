from collections import OrderedDict
import random

from callpower.apps.political_data.cache import political_data_cache
from callpower.apps.political_data.registry import get_country_data


INCLUDE_SPECIAL_BEFORE = "before"
INCLUDE_SPECIAL_AFTER = "after"
INCLUDE_SPECIAL_ONLY = "only"
INCLUDE_SPECIAL_FIRST = "first"
INCLUDE_SPECIAL_FALLBACK = "fallback"
SEGMENT_BY_LOCATION = "location"


def validate_location(location, campaign, cache=political_data_cache):
    campaign_data = get_country_data(campaign.country_code, cache=cache).get_campaign_type(campaign.campaign_type)
    return campaign_data.data_provider.get_location(campaign.locate_by, location)


def locate_targets(location, campaign, skip_special=False, cache=political_data_cache):
    if campaign.segment_by and campaign.segment_by != SEGMENT_BY_LOCATION:
        return []

    country_data = get_country_data(campaign.country_code, cache=cache)
    campaign_data = country_data.get_campaign_type(campaign.campaign_type)
    location_targets = campaign_data.get_targets_for_campaign(location, campaign)
    if getattr(campaign, "pk", None):
        special_targets = list(
            campaign.campaign_target_links.select_related("target").order_by("order", "id").values_list("target__key", flat=True)
        )
    else:
        special_targets = []

    if skip_special:
        return location_targets
    if not special_targets:
        return location_targets
    if campaign.target_ordering == "shuffle":
        random.shuffle(special_targets)

    if campaign.include_special == INCLUDE_SPECIAL_BEFORE:
        return list(OrderedDict.fromkeys(special_targets + location_targets))
    if campaign.include_special == INCLUDE_SPECIAL_AFTER:
        return list(OrderedDict.fromkeys(location_targets + special_targets))
    if campaign.include_special == INCLUDE_SPECIAL_ONLY:
        overlap = []
        for location_target in location_targets:
            for special_target in special_targets:
                if special_target.startswith(location_target) and special_target not in overlap:
                    overlap.append(special_target)
        if campaign.target_ordering == "shuffle":
            random.shuffle(overlap)
        return overlap
    if campaign.include_special == INCLUDE_SPECIAL_FIRST:
        first_targets = []
        for location_target in location_targets:
            for special_target in special_targets:
                if special_target.startswith(location_target) and special_target not in first_targets:
                    first_targets.insert(0, special_target)
        return list(OrderedDict.fromkeys(first_targets + special_targets))
    if campaign.include_special == INCLUDE_SPECIAL_FALLBACK:
        first_targets = []
        for location_target in location_targets:
            for special_target in special_targets:
                if special_target.startswith(location_target) and special_target not in first_targets:
                    first_targets.insert(0, special_target)
        return first_targets or location_targets
    return special_targets
