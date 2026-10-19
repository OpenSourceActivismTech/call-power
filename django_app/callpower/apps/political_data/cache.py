from django.core.cache import cache as django_cache


class PoliticalDataCache:
    def __init__(self):
        self._cache = django_cache
        self._keys = set()

    def get(self, key, default=None):
        value = self._cache.get(key)
        return default if value is None else value

    def set(self, key, value):
        self._keys.add(key)
        self._cache.set(key, value, timeout=None)

    def set_many(self, mapping):
        self._keys.update(mapping.keys())
        self._cache.set_many(mapping, timeout=None)

    def search_prefix(self, prefix):
        results = []
        for key in sorted(k for k in self._keys if k.startswith(prefix)):
            value = self.get(key)
            if isinstance(value, list):
                results.extend(value)
            elif value is not None:
                results.append(value)
        return results


political_data_cache = PoliticalDataCache()
