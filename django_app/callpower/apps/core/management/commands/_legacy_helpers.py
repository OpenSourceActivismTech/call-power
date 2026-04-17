from __future__ import annotations

from datetime import datetime
from getpass import getpass

from django.core.management.base import CommandError
from django.utils import timezone
from werkzeug.security import generate_password_hash

from callpower.apps.core.models import Campaign, CampaignTarget, LegacyUser, ScheduleCall
from callpower.apps.political_data.registry import COUNTRY_DATA, get_country_data
from callpower.apps.political_data.services import ensure_target_from_key


USER_ADMIN = 0
USER_ACTIVE = 2
USERNAME_LEN_MIN = 4
USERNAME_LEN_MAX = 25
PASSWORD_LEN_MIN = 6
PASSWORD_LEN_MAX = 64


def load_political_data(stdout):
    loaded = 0
    for country_code in COUNTRY_DATA:
        provider = get_country_data(country_code)
        loaded += provider.load_data()
        stdout.write(f"Loaded political data for {country_code.upper()}")
    return loaded


def fix_targets(campaign_id, stdout):
    campaign = Campaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise CommandError(f"Campaign {campaign_id} does not exist.")

    target_keys = list(
        campaign.campaign_target_links.select_related("target")
        .order_by("order", "id")
        .values_list("target__key", flat=True)
    )
    unique_keys = [key for key in dict.fromkeys(target_keys) if key]
    stdout.write(f"Got {len(target_keys)} targets, {len(unique_keys)} unique")

    CampaignTarget.objects.filter(campaign=campaign).delete()
    created_links = 0
    for index, target_key in enumerate(unique_keys):
        target = ensure_target_from_key(target_key)
        CampaignTarget.objects.create(
            campaign=campaign,
            target=target,
            order=index,
        )
        created_links += 1
        stdout.write(f"{index}: {target_key}")

    return campaign, created_links


def create_admin_user(username=None, password=None, email=None, stdin=None):
    stdin = stdin or input

    if username and LegacyUser.objects.filter(name=username).exists():
        raise CommandError(f"username {username} already exists")

    while username is None:
        candidate = stdin("Username: ").strip()
        if len(candidate) < USERNAME_LEN_MIN:
            print(f"username too short, must be at least {USERNAME_LEN_MIN} characters")
            continue
        if len(candidate) > USERNAME_LEN_MAX:
            print(f"username too long, must be less than {USERNAME_LEN_MAX} characters")
            continue
        if LegacyUser.objects.filter(name=candidate).exists():
            print("username already exists")
            continue
        username = candidate

    while email is None:
        candidate = stdin("Email: ").strip()
        if candidate:
            email = candidate

    while password is None:
        candidate = getpass("Password: ")
        password_confirm = getpass("Confirm: ")
        if candidate != password_confirm:
            print("passwords don't match")
            continue
        if len(candidate) < PASSWORD_LEN_MIN or len(candidate) > PASSWORD_LEN_MAX:
            print(f"password length must be between {PASSWORD_LEN_MIN} and {PASSWORD_LEN_MAX} characters")
            continue
        password = candidate

    now = timezone.now()
    user = LegacyUser.objects.create(
        name=username,
        email=email,
        password=generate_password_hash(password),
        role_code=USER_ADMIN,
        status_code=USER_ACTIVE,
        created_time=now,
        last_accessed=now,
    )
    return user


def stop_scheduled_calls(campaign_id, before_date, accept_all=False):
    campaign = Campaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise CommandError(f"Campaign {campaign_id} does not exist.")

    if isinstance(before_date, str):
        before_date = datetime.strptime(before_date, "%Y-%m-%d")
    aware_before = timezone.make_aware(before_date) if timezone.is_naive(before_date) else before_date

    scheduled_calls = list(
        ScheduleCall.objects.filter(campaign=campaign, created_at__lte=aware_before).order_by("id")
    )
    if not accept_all:
        raise CommandError("This command requires --accept-all in the Django migration.")

    for scheduled_call in scheduled_calls:
        scheduled_call.stop_job()
    return campaign, scheduled_calls


def restart_scheduled_calls(campaign_id, accept_all=False):
    if not accept_all:
        raise CommandError("This command requires --accept-all in the Django migration.")

    if campaign_id == "all":
        campaigns = Campaign.objects.filter(prompt_schedule=True, status_code=2).order_by("id")
    else:
        campaign = Campaign.objects.filter(pk=campaign_id).first()
        if not campaign:
            raise CommandError(f"Campaign {campaign_id} does not exist.")
        campaigns = [campaign]

    updated = []
    for campaign in campaigns:
        scheduled_calls = list(ScheduleCall.objects.filter(campaign=campaign, subscribed=True).order_by("id"))
        for scheduled_call in scheduled_calls:
            scheduled_call.start_job()
        updated.append((campaign, scheduled_calls))
    return updated
