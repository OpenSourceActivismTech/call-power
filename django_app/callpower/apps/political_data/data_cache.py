from callpower.apps.political_data.adapters import adapt_by_key
from callpower.apps.political_data.cache import political_data_cache
from callpower.apps.political_data.registry import get_country_data


def check_political_data_cache(key, cache=political_data_cache):
    adapter = adapt_by_key(key)
    adapted_key, _adapter_suffix = adapter.key(key)
    cached_obj = cache.get(adapted_key)

    if not cached_obj and adapted_key.startswith("us_state:openstates"):
        leg_id = key.split(":")[-1]
        leg = get_country_data("us", cache=cache).get_state_legid(leg_id)
        leg["cache_key"] = key
        cache.set(key, leg)
        cached_obj = leg

    if isinstance(cached_obj, list):
        data = adapter.target(cached_obj[0])
        offices = adapter.offices(cached_obj[0])
    elif isinstance(cached_obj, dict):
        data = adapter.target(cached_obj)
        offices = adapter.offices(cached_obj)
    else:
        data = cached_obj or {}
        offices = cached_obj.get("offices", []) if hasattr(cached_obj, "get") else []

    data["key"] = adapted_key
    data["offices"] = offices
    return data
