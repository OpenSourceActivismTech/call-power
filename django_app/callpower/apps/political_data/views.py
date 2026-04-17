from django.http import JsonResponse
from django.views.decorators.http import require_GET

from callpower.apps.political_data.registry import get_country_data


@require_GET
def search(request):
    country = request.GET.get("country", "us")
    keys = request.GET.getlist("key")
    if not keys:
        return JsonResponse({"status": "error", "message": "no key provided"}, status=400)
    data_provider = get_country_data(country)
    results = []
    for key in keys:
        results.extend(data_provider.cache_search(key))
    return JsonResponse({"status": "ok", "results": results})
