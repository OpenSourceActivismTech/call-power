import uuid
from datetime import timedelta

from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash


USER_ADMIN = 0
USER_STAFF = 1
USER_PARTNER = 2
USER_VIEWER = 3
USER_ROLE = {
    USER_ADMIN: "admin",
    USER_STAFF: "staff",
    USER_PARTNER: "partner",
    USER_VIEWER: "viewer",
}

USER_INACTIVE = 0
USER_NEW = 1
USER_ACTIVE = 2
USER_STATUS = {
    USER_INACTIVE: "inactive",
    USER_NEW: "new",
    USER_ACTIVE: "active",
}


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

    def __str__(self):
        return self.name

    @property
    def role(self):
        return USER_ROLE.get(self.role_code, "unknown")

    @property
    def status(self):
        return USER_STATUS.get(self.status_code, "unknown")

    def is_admin(self):
        return self.role_code == USER_ADMIN

    def is_active_user(self):
        return self.status_code == USER_ACTIVE

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password_hash(self.password, raw_password)


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

    def _audio_links(self):
        return self.campaign_audio_links.select_related("recording").filter(selected=True)

    def audio_or_default(self, key):
        campaign_audio = self._audio_links().filter(recording__key=key).first()
        if campaign_audio:
            return campaign_audio.recording, False
        return settings.CAMPAIGN_MESSAGE_DEFAULTS.get(key), True

    def audio(self, key):
        return self.audio_or_default(key)[0]

    @property
    def language_code(self):
        if self.campaign_language and self.country_code:
            return f"{self.campaign_language.lower()}-{self.country_code.upper()}"
        return "en-US"


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


class AudioRecording(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=255)
    file_storage = models.CharField(max_length=1024, blank=True, null=True)
    text_to_speech = models.TextField(blank=True, null=True)
    version = models.IntegerField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    hidden = models.BooleanField(default=False)

    class Meta:
        db_table = "campaign_recording"
        managed = False

    def storage_name(self):
        if not self.file_storage:
            return None

        raw = str(self.file_storage).strip()
        if not raw:
            return None

        if raw.startswith("http://") or raw.startswith("https://"):
            return raw

        media_root = Path(settings.MEDIA_ROOT)
        raw_path = Path(raw)

        if raw_path.is_absolute():
            try:
                return str(raw_path.relative_to(media_root)).replace("\\", "/")
            except ValueError:
                return raw_path.name

        if raw.startswith("uploads/"):
            return raw[len("uploads/") :]

        if raw.startswith("/uploads/"):
            return raw[len("/uploads/") :]

        return raw.lstrip("/")

    def file_url(self):
        storage_name = self.storage_name()
        if not storage_name:
            return None
        if storage_name.startswith("http://") or storage_name.startswith("https://"):
            return storage_name
        return f"{settings.MEDIA_URL.rstrip('/')}/{storage_name.lstrip('/')}"


class CampaignAudioRecording(models.Model):
    id = models.AutoField(primary_key=True)
    campaign = models.ForeignKey(
        Campaign,
        related_name="campaign_audio_links",
        db_column="campaign_id",
        on_delete=models.DO_NOTHING,
    )
    recording = models.ForeignKey(
        AudioRecording,
        related_name="campaign_audio_recordings",
        db_column="recording_id",
        on_delete=models.DO_NOTHING,
    )
    selected = models.BooleanField(default=False)

    class Meta:
        db_table = "campaign_audio_recordings"
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

    def scheduler_job(self):
        if not self.job_id:
            return None
        return ScheduledJob.objects.filter(job_key=self.job_id).first()

    def start_job(self, location=None):
        if not self.pk:
            self.save()

        now = timezone.now()
        job = self.scheduler_job()
        if job and location is None:
            location = (job.payload or {}).get("location")

        if not self.created_at:
            self.created_at = now
        if not self.time_to_call:
            self.time_to_call = now.time().replace(second=0, microsecond=0)

        if not self.job_id:
            self.job_id = str(uuid.uuid4())

        next_run_at = next_weekday_run(self.time_to_call, now)
        job_defaults = {
            "kind": ScheduledJob.KIND_SCHEDULED_CALL,
            "object_id": self.id,
            "active": True,
            "payload": {"location": location or ""},
            "next_run_at": next_run_at,
        }
        ScheduledJob.objects.update_or_create(job_key=self.job_id, defaults=job_defaults)
        self.subscribed = True
        self.save(update_fields=["created_at", "time_to_call", "job_id", "subscribed"])

    def stop_job(self):
        job = self.scheduler_job()
        if job:
            job.active = False
            job.save(update_fields=["active"])
        self.subscribed = False
        self.save(update_fields=["subscribed"])

    def is_running(self):
        job = self.scheduler_job()
        return bool(job and job.active)


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

    def has_schedule(self):
        return self.schedule in {"nightly", "hourly", "immediate"}

    def scheduler_job(self):
        if not self.job_id:
            return None
        return ScheduledJob.objects.filter(job_key=self.job_id).first()

    def start(self, schedule=None):
        if schedule:
            self.schedule = schedule
        if not self.pk:
            self.save()
        if not self.has_schedule():
            return False

        if not self.job_id:
            self.job_id = str(uuid.uuid4())

        now = timezone.now()
        job_defaults = {
            "kind": ScheduledJob.KIND_CRM_SYNC,
            "object_id": self.id,
            "active": True,
            "payload": {"campaign_id": self.campaign_id},
            "next_run_at": next_sync_run(self.schedule, now),
        }
        ScheduledJob.objects.update_or_create(job_key=self.job_id, defaults=job_defaults)
        self.save(update_fields=["job_id", "schedule"])
        return True

    def stop(self):
        job = self.scheduler_job()
        if not job:
            return False
        job.active = False
        job.save(update_fields=["active"])
        return True

    def is_running(self):
        job = self.scheduler_job()
        return bool(job and job.active)

    def sync_calls(self):
        from callpower.crm_sync.service import sync_campaign_calls

        return sync_campaign_calls(self)


class SyncCall(models.Model):
    id = models.AutoField(primary_key=True)
    created_time = models.DateTimeField(auto_now_add=True)
    call = models.ForeignKey(
        Call,
        related_name="sync_records",
        db_column="call_id",
        on_delete=models.CASCADE,
    )
    saved = models.BooleanField(default=False)
    crm_message = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "sync_call"


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


class ScheduledJob(models.Model):
    KIND_SCHEDULED_CALL = "scheduled_call"
    KIND_CRM_SYNC = "crm_sync"

    KIND_CHOICES = [
        (KIND_SCHEDULED_CALL, "Scheduled call"),
        (KIND_CRM_SYNC, "CRM sync"),
    ]

    job_key = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    object_id = models.IntegerField()
    active = models.BooleanField(default=True)
    payload = models.JSONField(default=dict, blank=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    last_run_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "django_scheduler_job"
        ordering = ["next_run_at", "id"]


def next_weekday_run(time_to_call, base_time):
    candidate = base_time.replace(
        hour=time_to_call.hour,
        minute=time_to_call.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= base_time:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def next_sync_run(schedule, base_time):
    normalized = (schedule or "hourly").lower()
    base = base_time.replace(second=0, microsecond=0)

    if normalized == "immediate":
        return base + timedelta(minutes=1)
    if normalized == "nightly":
        candidate = base.replace(hour=23, minute=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate

    candidate = base.replace(minute=0)
    if candidate <= base:
        candidate += timedelta(hours=1)
    return candidate
