from copy import deepcopy

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from callpower.apps.calls import views as call_views
from callpower.apps.core.models import Call, Campaign


def _campaign_or_404(campaign_id):
    campaign = Campaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise Http404("Campaign not found")
    return campaign


def _installed_org():
    return getattr(settings, "INSTALLED_ORG", "OpenSourceActivism.tech")


def _base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def _embed_context(request, campaign):
    return {
        "campaign": campaign,
        "dsn_public_key": getattr(settings, "SENTRY_DSN_PUBLIC_KEY", ""),
        "base_url": _base_url(request),
    }


def index(request):
    return render(
        request,
        "public/index.html",
        {
            "installed_org": _installed_org(),
        },
    )


@require_GET
def campaign_page(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    return render(
        request,
        "public/campaign_page.html",
        {
            "campaign": campaign,
            "standalone": True,
            "base_url": _base_url(request),
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def legacy_call_redirect(request):
    return call_views.create(request)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def legacy_call_incoming(request):
    return call_views.incoming(request)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def legacy_call_status(request):
    return call_views.status_callback(request)


@require_GET
@cache_page(60 * 10)
def campaign_embed_js(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    content = render(request, "public/embed.js", _embed_context(request, campaign)).content
    return HttpResponse(content, content_type="application/javascript")


@require_GET
@cache_page(60 * 10)
def campaign_form_js(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    content = render(
        request,
        "public/CallPowerForm.js",
        {"campaign": campaign, "base_url": _base_url(request)},
    ).content
    return HttpResponse(content, content_type="application/javascript")


@require_GET
@cache_page(60 * 10)
@xframe_options_exempt
def campaign_embed_iframe(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    return render(request, "public/embed_iframe.html", {"campaign": campaign, "base_url": _base_url(request)})


@require_GET
def campaign_embed_code(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    embed = deepcopy(campaign.embed or {})
    temp_params = {
        "type": request.GET.get("embed_type", embed.get("type", "")),
        "form_sel": request.GET.get("embed_form_sel") or embed.get("form_sel"),
        "phone_sel": request.GET.get("embed_phone_sel") or embed.get("phone_sel"),
        "location_sel": request.GET.get("embed_location_sel") or embed.get("location_sel"),
        "custom_css": request.GET.get("embed_custom_css") or embed.get("custom_css"),
        "custom_js": request.GET.get("embed_custom_js") or embed.get("custom_js"),
        "custom_onload": request.GET.get("embed_custom_onload") or embed.get("custom_onload"),
        "script_display": request.GET.get("embed_script_display") or embed.get("script_display"),
        "phone_display": request.GET.get("embed_phone_display") or embed.get("phone_display"),
        "redirect": request.GET.get("embed_redirect") or embed.get("redirect"),
        "script": request.GET.get("embed_script") or embed.get("script", ""),
    }
    campaign.embed = temp_params
    return render(request, "public/embed_code.html", {"campaign": campaign, "base_url": _base_url(request)})


@require_GET
@cache_page(60 * 10)
def campaign_count(request, campaign_id):
    campaign = _campaign_or_404(campaign_id)
    count = Call.objects.filter(campaign=campaign, status="completed").count()
    return JsonResponse({"count": count, "campaignId": campaign.id})
