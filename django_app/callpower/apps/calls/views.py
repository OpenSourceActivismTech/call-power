import hashlib
import random
from datetime import timedelta
from urllib.parse import urlencode

import phonenumbers
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from twilio.rest import Client
from twilio.twiml.voice_response import Dial, Gather, VoiceResponse

from callpower.apps.core.models import Call, Campaign, Session, Target
from callpower.apps.political_data.lookup import locate_targets, validate_location
from callpower.apps.political_data.services import ensure_target_from_key


SEGMENT_BY_LOCATION = "location"
SEGMENT_BY_CUSTOM = "custom"
LOCATION_POSTAL = "postal"
LOCATION_DISTRICT = "district"
TWILIO_TTS_LANGUAGES = {
    "da-DK",
    "de-DE",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-IN",
    "en-US",
    "ca-ES",
    "es-ES",
    "es-MX",
    "fi-FI",
    "fr-CA",
    "fr-FR",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "nb-NO",
    "nl-NL",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ru-RU",
    "sv-SE",
    "zh-CN",
    "zh-HK",
    "zh-TW",
}


def twiml_response(response):
    return HttpResponse(str(response), content_type="text/xml")


def json_error(message, status=400):
    return JsonResponse({"status": status, "error": message}, status=status)


def request_data(request):
    return request.POST if request.method == "POST" else request.GET


def build_url(request, route_name, params):
    return request.build_absolute_uri(f"{reverse(route_name)}?{urlencode(params, doseq=True)}")


def normalize_phone(number, country_code="US"):
    try:
        parsed = phonenumbers.parse(number, country_code)
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return number


def hash_phone(number):
    return hashlib.sha256(number.encode("ascii")).hexdigest()


def twilio_client():
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise RuntimeError("Missing Twilio credentials")
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def campaign_phone_numbers(campaign, region_code=None):
    links = campaign.campaign_phone_links.select_related("phone").all()
    numbers = []
    for link in links:
        if link.phone and link.phone.number:
            numbers.append(link.phone.number)
    return numbers


def campaign_language(campaign):
    if campaign.campaign_language and campaign.country_code:
        value = f"{campaign.campaign_language.lower()}-{campaign.country_code.upper()}"
    else:
        value = "en-US"
    return value if value in TWILIO_TTS_LANGUAGES else "en-US"


def speak(response, message, *, lang="en-US", **kwargs):
    rendered = message.format(**kwargs) if kwargs else message
    response.say(rendered, voice="alice", language=lang)


def parse_params(request, inbound=False):
    data = request_data(request)
    params = {
        "campaign_id": data.get("campaignId"),
        "scheduled": data.get("scheduled"),
        "schedule_skip": data.get("scheduleSkip"),
        "session_id": data.get("sessionId"),
        "target_ids": data.getlist("targetIds") if hasattr(data, "getlist") else [],
        "user_phone": data.get("userPhone"),
        "user_country": (data.get("userCountry") or "US").upper(),
        "user_location": data.get("userLocation"),
        "user_ip_address": data.get("userIPAddress") or request.META.get("REMOTE_ADDR"),
    }

    if not params["campaign_id"]:
        raise ValueError("campaignId required")
    if not inbound and not params["user_phone"]:
        raise ValueError("userPhone required")

    campaign = Campaign.objects.filter(pk=params["campaign_id"]).first()
    if not campaign:
        campaign = Campaign.objects.filter(name=params["campaign_id"]).first()
    if not campaign:
        raise ValueError(f"invalid campaignId {params['campaign_id']}")

    return params, campaign


def ordered_campaign_targets(campaign):
    links = campaign.campaign_target_links.select_related("target").order_by("order", "id").all()
    return [link.target for link in links if link.target]


def resolve_targets(params, campaign):
    if params["target_ids"]:
        targets = []
        for value in params["target_ids"]:
            target = Target.objects.filter(key=value).first() or ensure_target_from_key(value)
            if target:
                targets.append(target)
        return targets

    if campaign.segment_by == SEGMENT_BY_CUSTOM:
        targets = ordered_campaign_targets(campaign)
        if campaign.target_ordering == "shuffle":
            random.shuffle(targets)
        return targets

    if campaign.segment_by == SEGMENT_BY_LOCATION and params.get("user_location"):
        keys = locate_targets(params["user_location"], campaign)
        return [ensure_target_from_key(key) for key in keys]

    return ordered_campaign_targets(campaign)


def intro_wait_human(request, params, campaign):
    resp = VoiceResponse()
    speak(resp, "Welcome to {name}.", name=campaign.name, lang=campaign_language(campaign))
    action = build_url(request, "call-make-calls", twilio_params(params))
    gather = Gather(num_digits=1, timeout=10, method="POST", action=action)
    speak(gather, "Press star to get started.", lang=campaign_language(campaign))
    resp.append(gather)
    speak(resp, "Goodbye.", lang=campaign_language(campaign))
    return twiml_response(resp)


def intro_location_gather(request, params, campaign):
    resp = VoiceResponse()
    speak(resp, f"Welcome to {campaign.name}.", lang=campaign_language(campaign))
    return location_gather(request, resp, params, campaign)


def location_gather(request, resp, params, campaign):
    action = build_url(request, "call-location-parse", twilio_params(params))
    gather = Gather(num_digits=5, timeout=10, method="POST", action=action)
    speak(gather, "Please enter your zip code.", lang=campaign_language(campaign))
    resp.append(gather)
    speak(resp, "We could not understand that location.", lang=campaign_language(campaign))
    return twiml_response(resp)


def twilio_params(params):
    data = {
        "campaignId": params["campaign_id"],
        "scheduled": params.get("scheduled") or "",
        "scheduleSkip": params.get("schedule_skip") or "",
        "sessionId": params.get("session_id") or "",
        "userPhone": params.get("user_phone") or "",
        "userCountry": params.get("user_country") or "",
        "userLocation": params.get("user_location") or "",
        "userIPAddress": params.get("user_ip_address") or "",
    }
    target_ids = params.get("target_ids") or []
    if target_ids:
        data["targetIds"] = target_ids
    return data


def session_from_params(params):
    if not params.get("session_id"):
        return None
    return Session.objects.filter(pk=params["session_id"]).first()


@csrf_exempt
@require_http_methods(["GET", "POST"])
def create(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    phone_numbers = campaign_phone_numbers(campaign, params["user_country"])
    if not phone_numbers:
        return json_error("no numbers available for campaign in region")

    user_phone = normalize_phone(params["user_phone"], params["user_country"])
    targets = resolve_targets(params, campaign)
    if campaign.call_maximum:
        targets = targets[: campaign.call_maximum]
    params["target_ids"] = [target.key for target in targets if target.key]

    from_number = random.choice(phone_numbers)
    session = Session(
        campaign=campaign,
        timestamp=timezone.now(),
        location=params["user_location"],
        from_number=from_number,
        status="initiated",
        direction="outbound",
    )
    if settings.LOG_PHONE_NUMBERS and params["user_phone"]:
        session.phone_hash = hash_phone(params["user_phone"])
    ref = request_data(request).get("ref")
    if ref:
        session.referral_code = ref[:64]
    session.save()
    params["session_id"] = session.id

    try:
        call = twilio_client().calls.create(
            to=user_phone,
            from_=from_number,
            url=build_url(request, "call-connection", twilio_params(params)),
            timeout=settings.TWILIO_TIMEOUT,
            status_callback=build_url(request, "call-status-callback", twilio_params(params)),
            status_callback_event=["ringing", "completed"],
            record=bool(request_data(request).get("record", False)),
        )
    except Exception as exc:
        return json_error(str(exc))

    target_response = {
        "segment": campaign.segment_by,
        "objects": [
            {"name": target.name, "title": target.title, "phone": target.number}
            for target in targets
            if target.number
        ],
    }
    embed = campaign.embed or {}
    return JsonResponse(
        {
            "campaign": {0: "archived", 1: "paused", 2: "live"}.get(campaign.status_code, "unknown"),
            "call": call.status,
            "script": embed.get("script", ""),
            "redirect": embed.get("redirect", ""),
            "fromNumber": from_number,
            "targets": target_response,
        },
        status=200 if call.status != "failed" else 500,
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def incoming(request):
    try:
        params, campaign = parse_params(request, inbound=True)
    except ValueError as exc:
        return json_error(str(exc))

    if campaign.status_code == 0:
        resp = VoiceResponse()
        speak(resp, "This campaign is complete.", lang=campaign_language(campaign))
        return twiml_response(resp)

    params["user_phone"] = request_data(request).get("From")
    campaign_number = request_data(request).get("To")
    session = Session(
        campaign=campaign,
        timestamp=timezone.now(),
        from_number=campaign_number,
        status="initiated",
        direction="inbound",
    )
    if settings.LOG_PHONE_NUMBERS and params["user_phone"]:
        session.phone_hash = hash_phone(params["user_phone"])
    session.save()
    params["session_id"] = session.id

    if campaign.segment_by == SEGMENT_BY_LOCATION and campaign.locate_by in [LOCATION_POSTAL, LOCATION_DISTRICT]:
        return intro_location_gather(request, params, campaign)
    return intro_wait_human(request, params, campaign)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def connection(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    if campaign.segment_by == SEGMENT_BY_LOCATION and campaign.locate_by in [LOCATION_POSTAL, LOCATION_DISTRICT] and not params["user_location"]:
        return intro_location_gather(request, params, campaign)
    return intro_wait_human(request, params, campaign)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def location_parse(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    location = request_data(request).get("Digits", "")[:5]
    if not location:
        resp = VoiceResponse()
        speak(resp, "We could not understand that location.", lang=campaign_language(campaign))
        return location_gather(request, resp, params, campaign)

    if not validate_location(location, campaign):
        resp = VoiceResponse()
        speak(resp, "We could not understand that location.", lang=campaign_language(campaign))
        return location_gather(request, resp, params, campaign)

    params["user_location"] = location
    session = session_from_params(params)
    if session and not session.location:
        session.location = location
        session.save(update_fields=["location"])
    resp = VoiceResponse()
    resp.redirect(build_url(request, "call-make-calls", twilio_params(params)))
    return twiml_response(resp)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def make_calls(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    targets = resolve_targets(params, campaign)
    if campaign.call_maximum:
        targets = targets[: campaign.call_maximum]
    params["target_ids"] = [target.key for target in targets if target.key]

    resp = VoiceResponse()
    if not params["target_ids"]:
        speak(resp, "We could not find any targets for this campaign.", lang=campaign_language(campaign))
        resp.hangup()
        return twiml_response(resp)

    speak(
        resp,
        "We will connect you to {count} target{suffix}.",
        count=len(params["target_ids"]),
        suffix="" if len(params["target_ids"]) == 1 else "s",
        lang=campaign_language(campaign),
    )
    redirect_params = twilio_params(params)
    redirect_params["call_index"] = 0
    resp.redirect(build_url(request, "call-make-single", redirect_params))
    return twiml_response(resp)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def make_single(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    call_index = int(request_data(request).get("call_index", 0))
    targets = resolve_targets(params, campaign)
    if call_index >= len(targets):
        resp = VoiceResponse()
        speak(resp, "Thank you for calling.", lang=campaign_language(campaign))
        return twiml_response(resp)

    target = targets[call_index]
    if not target.number:
        resp = VoiceResponse()
        speak(resp, "This target does not have a callable number.", lang=campaign_language(campaign))
        redirect_params = twilio_params(params)
        redirect_params["call_index"] = call_index + 1
        resp.redirect(build_url(request, "call-make-single", redirect_params))
        return twiml_response(resp)

    resp = VoiceResponse()
    speak(
        resp,
        "Connecting you to {title} {name}.",
        title=target.title or "",
        name=target.name,
        lang=campaign_language(campaign),
    )
    user_phone = normalize_phone(params["user_phone"], params["user_country"])
    dial = Dial(
        caller_id=user_phone,
        time_limit=settings.TWILIO_TIME_LIMIT,
        timeout=settings.TWILIO_TIMEOUT,
        hangup_on_star=True,
        action=build_url(
            request,
            "call-complete",
            {**twilio_params(params), "call_index": call_index},
        ),
    )
    dial.number(target.number)
    resp.append(dial)
    return twiml_response(resp)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@transaction.atomic
def complete(request):
    try:
        params, campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    call_index = int(request_data(request).get("call_index", 0))
    targets = resolve_targets(params, campaign)
    if call_index >= len(targets):
        return twiml_response(VoiceResponse())

    target = targets[call_index]
    Call.objects.create(
        session_id=params["session_id"],
        campaign=campaign,
        target=target,
        timestamp=timezone.now(),
        call_id=request_data(request).get("CallSid"),
        status=request_data(request).get("DialCallStatus", "unknown"),
        duration=int(request_data(request).get("DialCallDuration") or 0),
    )

    resp = VoiceResponse()
    if call_index == len(targets) - 1:
        speak(resp, "Thank you for calling.", lang=campaign_language(campaign))
    else:
        speak(resp, "Next call.", lang=campaign_language(campaign))
        redirect_params = twilio_params(params)
        redirect_params["call_index"] = call_index + 1
        resp.redirect(build_url(request, "call-make-single", redirect_params))
    return twiml_response(resp)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def status_callback(request):
    try:
        params, _campaign = parse_params(request)
    except ValueError as exc:
        return json_error(str(exc))

    session = session_from_params(params)
    if not session:
        return JsonResponse(
            {
                "phoneNumber": request_data(request).get("From", ""),
                "callStatus": "unknown",
                "message": "no sessionId passed, unable to update status",
                "campaignId": params["campaign_id"],
            }
        )

    if request_data(request).get("CallStatus") == "ringing" and session.timestamp:
        session.queue_delay = timezone.now() - session.timestamp
        session.save(update_fields=["queue_delay"])

    if request_data(request).get("CallDuration"):
        session.status = request_data(request).get("CallStatus", "unknown")
        session.duration = int(request_data(request).get("CallDuration") or 0)
        session.save(update_fields=["status", "duration"])

    return JsonResponse(
        {
            "phoneNumber": request_data(request).get("To", ""),
            "callStatus": request_data(request).get("CallStatus"),
            "targetIds": params["target_ids"],
            "campaignId": params["campaign_id"],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def status_inbound(request):
    try:
        params, campaign = parse_params(request, inbound=True)
    except ValueError as exc:
        return json_error(str(exc))

    user_phone = request_data(request).get("From", "")
    session = (
        Session.objects.filter(
            phone_hash=hash_phone(user_phone) if user_phone else "",
            status="initiated",
            direction="inbound",
            campaign=campaign,
        )
        .order_by("-timestamp")
        .first()
    )
    if not session:
        return JsonResponse(
            {
                "phoneNumber": user_phone,
                "callStatus": "unknown",
                "message": "unable to find CallSession matching campaign and phone",
                "campaignId": params["campaign_id"],
            }
        )

    session.status = request_data(request).get("CallStatus", "unknown")
    session.duration = int(request_data(request).get("CallDuration") or 0)
    session.save(update_fields=["status", "duration"])
    return JsonResponse(
        {
            "phoneNumber": user_phone,
            "callStatus": session.status,
            "campaignId": params["campaign_id"],
        }
    )
