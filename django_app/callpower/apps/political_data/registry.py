from importlib import import_module

from callpower.apps.political_data.cache import political_data_cache


COUNTRY_CHOICES = [
    ("us", "United States"),
    ("ca", "Canada"),
    ("fr", "France"),
    ("de", "Germany"),
    ("es", "Spain"),
    ("ir", "Ireland"),
    ("it", "Italy"),
    ("pl", "Poland"),
    ("uk", "United Kingdom"),
]

COUNTRY_DATA = {
    "us": "callpower.apps.political_data.providers.us.USDataProvider",
    "ca": "callpower.apps.political_data.providers.ca.CADataProvider",
    "fr": "callpower.apps.political_data.providers.eu.FRDataProvider",
    "de": "callpower.apps.political_data.providers.eu.DEDataProvider",
    "es": "callpower.apps.political_data.providers.eu.ESDataProvider",
    "ir": "callpower.apps.political_data.providers.eu.IRDataProvider",
    "it": "callpower.apps.political_data.providers.eu.ITDataProvider",
    "pl": "callpower.apps.political_data.providers.eu.PLDataProvider",
    "uk": "callpower.apps.political_data.providers.eu.UKDataProvider",
}


def get_country_data(country_code, cache=political_data_cache):
    module_name, class_name = COUNTRY_DATA[country_code.lower()].rsplit(".", 1)
    provider_class = getattr(import_module(module_name), class_name)
    provider = provider_class(cache=cache)
    ensure_loaded(country_code.lower(), provider)
    return provider


def ensure_loaded(country_code, provider):
    marker = f"political_data:{country_code.lower()}"
    if provider.cache_get(marker) is None:
        provider.load_data()
