from django.utils import timezone
from django.db import models
from django.db.models import Count, Q


class LegacyUser(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    openid = models.CharField(max_length=255, blank=True, null=True)
    activation_key = models.CharField(max_length=255, blank=True, null=True)
    created_time = models.DateTimeField(blank=True, null=True)
    last_accessed = models.DateTimeField(blank=True, null=True)
    phone = models.CharField(max_length=64, blank=True, null=True)
    password = models.CharField(max_length=255)
    role_code = models.SmallIntegerField(default=1)
    status_code = models.SmallIntegerField(default=1)

    class Meta:
        db_table = "user_user"
        managed = False


class Campaign(models.Model):
    id = models.AutoField(primary_key=True)
    created_time = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=500)
    country_code = models.CharField(max_length=255, blank=True, null=True)
    campaign_type = models.CharField(max_length=255, blank=True, null=True)
    campaign_state = models.CharField(max_length=255, blank=True, null=True)
    campaign_subtype = models.CharField(max_length=255, blank=True, null=True)
    campaign_language = models.CharField(max_length=255, blank=True, null=True)
    segment_by = models.CharField(max_length=255, blank=True, null=True)
    locate_by = models.CharField(max_length=255, blank=True, null=True)
    include_special = models.CharField(max_length=255, blank=True, null=True)
    target_ordering = models.CharField(max_length=255, blank=True, null=True)
    target_shuffle_chamber = models.BooleanField(default=True)
    target_offices = models.CharField(max_length=255, blank=True, null=True)
    call_maximum = models.SmallIntegerField(blank=True, null=True)
    allow_call_in = models.BooleanField(default=False)
    allow_intl_calls = models.BooleanField(default=False)
    prompt_schedule = models.BooleanField(default=False)
    status_code = models.SmallIntegerField(default=0)
    embed = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "campaign_campaign"
        managed = False
        ordering = ["-status_code", "-id"]

    def __str__(self):
        return self.name

    @property
    def completed_calls_count(self):
        return getattr(self, "completed_calls", 0)

    @property
    def total_sessions_count(self):
        return getattr(self, "total_sessions", 0)

    @classmethod
    def with_dashboard_counts(cls):
        return cls.objects.annotate(
            completed_calls=Count(
                "call_records",
                filter=Q(call_records__status="completed"),
                distinct=True,
            ),
            total_sessions=Count("sessions", distinct=True),
        )


class Target(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    district = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=64, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "campaign_target"
        managed = False

    def __str__(self):
        return self.name


class TargetOffice(models.Model):
    id = models.AutoField(primary_key=True)
    uid = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    latlon = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=64, blank=True, null=True)
    target = models.ForeignKey(
        Target,
        related_name="offices",
        db_column="target_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "campaign_target_office"
        managed = False


class CampaignPhoneNumber(models.Model):
    id = models.AutoField(primary_key=True)
    campaign = models.ForeignKey(
        Campaign,
        related_name="campaign_phone_links",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
    )
    phone = models.ForeignKey(
        "TwilioPhoneNumber",
        related_name="campaign_links",
        db_column="phone_id",
        on_delete=models.DO_NOTHING,
    )

    class Meta:
        db_table = "campaign_phone_numbers"
        managed = False


class CampaignTarget(models.Model):
    id = models.AutoField(primary_key=True)
    campaign = models.ForeignKey(
        Campaign,
        related_name="campaign_target_links",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
    )
    target = models.ForeignKey(
        Target,
        related_name="campaign_links",
        db_column="target_id",
        on_delete=models.DO_NOTHING,
    )
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "campaign_target_sets"
        managed = False


class Session(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    campaign = models.ForeignKey(
        Campaign,
        related_name="sessions",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    phone_hash = models.CharField(max_length=64, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    referral_code = models.CharField(max_length=64, blank=True, null=True)
    from_number = models.CharField(max_length=16, blank=True, null=True)
    twilio_id = models.CharField(max_length=40, blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=25, blank=True, null=True)
    direction = models.CharField(max_length=25, blank=True, null=True)
    queue_delay = models.DurationField(blank=True, null=True)

    class Meta:
        db_table = "calls_session"
        managed = False


class Call(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    session = models.ForeignKey(
        Session,
        related_name="calls",
        db_column="session_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    campaign = models.ForeignKey(
        Campaign,
        related_name="call_records",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    target = models.ForeignKey(
        Target,
        related_name="calls",
        db_column="target_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    call_id = models.CharField(max_length=40, blank=True, null=True)
    status = models.CharField(max_length=25, blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "calls"
        managed = False
        ordering = ["-timestamp", "-id"]


class ScheduleCall(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(blank=True, null=True)
    subscribed = models.BooleanField(default=True)
    time_to_call = models.TimeField(blank=True, null=True)
    last_called = models.DateTimeField(blank=True, null=True)
    num_calls = models.IntegerField(default=0)
    campaign = models.ForeignKey(
        Campaign,
        related_name="scheduled_calls",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    phone_number = models.CharField(max_length=64, blank=True, null=True)
    job_id = models.CharField(max_length=36, blank=True, null=True)

    class Meta:
        db_table = "schedule_call"
        managed = False


class TwilioPhoneNumber(models.Model):
    id = models.AutoField(primary_key=True)
    twilio_sid = models.CharField(max_length=64, blank=True, null=True)
    twilio_app = models.CharField(max_length=64, blank=True, null=True)
    call_in_allowed = models.BooleanField(default=False)
    call_in_campaign = models.ForeignKey(
        Campaign,
        related_name="call_in_numbers",
        db_column="call_in_campaign_id",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    number = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        db_table = "campaign_phone"
        managed = False


class SyncCampaign(models.Model):
    id = models.AutoField(primary_key=True)
    job_id = models.CharField(max_length=36, blank=True, null=True)
    created_time = models.DateTimeField(blank=True, null=True)
    last_sync_time = models.DateTimeField(blank=True, null=True)
    campaign = models.OneToOneField(
        Campaign,
        related_name="sync_campaign",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
    )
    schedule = models.CharField(max_length=25, default="hourly")
    crm_id = models.CharField(max_length=40, blank=True, null=True)
    crm_key = models.CharField(max_length=40, blank=True, null=True)

    class Meta:
        db_table = "sync_campaign"
        managed = False


class Blocklist(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    expires = models.DurationField(blank=True, null=True)
    phone_number = models.CharField(max_length=64, blank=True, null=True)
    phone_hash = models.CharField(max_length=64, blank=True, null=True)
    ip_address = models.CharField(max_length=16, blank=True, null=True)
    hits = models.IntegerField(default=0)

    class Meta:
        db_table = "admin_blocklist"
        managed = False

    def is_active(self):
        if self.expires and self.timestamp:
            return timezone.now() <= (self.timestamp + self.expires)
        return True
