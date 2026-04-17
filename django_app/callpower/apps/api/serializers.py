from django.db import transaction
from rest_framework import serializers

from callpower.apps.core.models import (
    AudioRecording,
    Campaign,
    CampaignAudioRecording,
    CampaignPhoneNumber,
    CampaignTarget,
    ScheduleCall,
    SyncCampaign,
    Target,
    TwilioPhoneNumber,
)


class CampaignSummarySerializer(serializers.ModelSerializer):
    completed_calls = serializers.IntegerField(source="completed_calls_count", read_only=True)
    total_sessions = serializers.IntegerField(source="total_sessions_count", read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "country_code",
            "campaign_type",
            "campaign_state",
            "campaign_subtype",
            "status_code",
            "allow_call_in",
            "prompt_schedule",
            "completed_calls",
            "total_sessions",
        ]


class TwilioPhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwilioPhoneNumber
        fields = ["id", "number", "call_in_allowed", "call_in_campaign_id"]


class TargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Target
        fields = ["id", "key", "title", "name", "district", "number", "location"]


class CampaignAudioRecordingSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    selected = serializers.SerializerMethodField()

    class Meta:
        model = AudioRecording
        fields = [
            "id",
            "key",
            "version",
            "description",
            "text_to_speech",
            "hidden",
            "file_url",
            "selected",
        ]

    def get_file_url(self, obj):
        return obj.file_url()

    def get_selected(self, obj):
        campaign = self.context.get("campaign")
        if not campaign:
            return False
        return CampaignAudioRecording.objects.filter(
            campaign=campaign,
            recording=obj,
            selected=True,
        ).exists()


class CampaignDetailSerializer(serializers.ModelSerializer):
    phone_number_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
    )
    assigned_phone_numbers = serializers.SerializerMethodField()
    target_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
    )
    assigned_targets = serializers.SerializerMethodField()
    embed_type = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_script = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_form_sel = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_phone_sel = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_location_sel = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_custom_css = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_custom_js = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_custom_onload = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_script_display = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_phone_display = serializers.CharField(write_only=True, required=False, allow_blank=True)
    embed_redirect = serializers.CharField(write_only=True, required=False, allow_blank=True)
    crm_sync = serializers.BooleanField(write_only=True, required=False, default=False)
    crm_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    crm_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    sync_schedule = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "country_code",
            "campaign_type",
            "campaign_state",
            "campaign_subtype",
            "campaign_language",
            "segment_by",
            "locate_by",
            "include_special",
            "target_ordering",
            "target_shuffle_chamber",
            "target_offices",
            "call_maximum",
            "allow_call_in",
            "allow_intl_calls",
            "prompt_schedule",
            "status_code",
            "embed",
            "assigned_phone_numbers",
            "phone_number_ids",
            "assigned_targets",
            "target_ids",
            "embed_type",
            "embed_script",
            "embed_form_sel",
            "embed_phone_sel",
            "embed_location_sel",
            "embed_custom_css",
            "embed_custom_js",
            "embed_custom_onload",
            "embed_script_display",
            "embed_phone_display",
            "embed_redirect",
            "crm_sync",
            "crm_id",
            "crm_key",
            "sync_schedule",
        ]
        read_only_fields = ["id", "assigned_phone_numbers", "assigned_targets"]

    def get_assigned_phone_numbers(self, obj):
        links = obj.campaign_phone_links.select_related("phone").all()
        return TwilioPhoneNumberSerializer([link.phone for link in links], many=True).data

    def get_assigned_targets(self, obj):
        links = obj.campaign_target_links.select_related("target").order_by("order", "id").all()
        return TargetSerializer([link.target for link in links], many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        embed = instance.embed or {}
        data.update(
            {
                "embed_type": embed.get("type", ""),
                "embed_script": embed.get("script", ""),
                "embed_form_sel": embed.get("form_sel", ""),
                "embed_phone_sel": embed.get("phone_sel", ""),
                "embed_location_sel": embed.get("location_sel", ""),
                "embed_custom_css": embed.get("custom_css", ""),
                "embed_custom_js": embed.get("custom_js", ""),
                "embed_custom_onload": embed.get("custom_onload", ""),
                "embed_script_display": embed.get("script_display", ""),
                "embed_phone_display": embed.get("phone_display", ""),
                "embed_redirect": embed.get("redirect", ""),
                "crm_sync": hasattr(instance, "sync_campaign") and instance.sync_campaign is not None,
                "crm_id": getattr(getattr(instance, "sync_campaign", None), "crm_id", "") or "",
                "crm_key": getattr(getattr(instance, "sync_campaign", None), "crm_key", "") or "",
                "sync_schedule": getattr(getattr(instance, "sync_campaign", None), "schedule", "") or "",
            }
        )
        return data

    def _sync_phone_numbers(self, campaign, phone_number_ids):
        if phone_number_ids is None:
            return

        existing_ids = set(
            campaign.campaign_phone_links.values_list("phone_id", flat=True)
        )
        desired_ids = set(phone_number_ids)

        for stale_id in existing_ids - desired_ids:
            CampaignPhoneNumber.objects.filter(
                campaign=campaign,
                phone_id=stale_id,
            ).delete()

        for phone_id in desired_ids - existing_ids:
            CampaignPhoneNumber.objects.create(campaign=campaign, phone_id=phone_id)

    def _sync_targets(self, campaign, target_ids):
        if target_ids is None:
            return

        existing_ids = list(
            campaign.campaign_target_links.order_by("order", "id").values_list("target_id", flat=True)
        )
        desired_ids = list(dict.fromkeys(target_ids))

        CampaignTarget.objects.filter(campaign=campaign).delete()
        for order, target_id in enumerate(desired_ids):
            CampaignTarget.objects.create(
                campaign=campaign,
                target_id=target_id,
                order=order,
            )

    def _sync_embed_settings(self, validated_data):
        embed_type = validated_data.pop("embed_type", None)
        embed_script = validated_data.pop("embed_script", None)
        embed_form_sel = validated_data.pop("embed_form_sel", None)
        embed_phone_sel = validated_data.pop("embed_phone_sel", None)
        embed_location_sel = validated_data.pop("embed_location_sel", None)
        embed_custom_css = validated_data.pop("embed_custom_css", None)
        embed_custom_js = validated_data.pop("embed_custom_js", None)
        embed_custom_onload = validated_data.pop("embed_custom_onload", None)
        embed_script_display = validated_data.pop("embed_script_display", None)
        embed_phone_display = validated_data.pop("embed_phone_display", None)
        embed_redirect = validated_data.pop("embed_redirect", None)

        touched = any(
            value is not None
            for value in [
                embed_type,
                embed_script,
                embed_form_sel,
                embed_phone_sel,
                embed_location_sel,
                embed_custom_css,
                embed_custom_js,
                embed_custom_onload,
                embed_script_display,
                embed_phone_display,
                embed_redirect,
            ]
        )
        if not touched:
            return validated_data

        embed = {}
        if embed_type == "custom":
            embed = {
                "type": embed_type,
                "form_sel": embed_form_sel or "",
                "phone_sel": embed_phone_sel or "",
                "location_sel": embed_location_sel or "",
                "custom_css": embed_custom_css or "",
                "custom_js": embed_custom_js or "",
                "custom_onload": embed_custom_onload or "",
                "script_display": embed_script_display or "",
                "phone_display": embed_phone_display or "",
                "redirect": embed_redirect or "",
            }
        elif embed_type == "iframe":
            embed = {
                "type": embed_type,
                "custom_css": embed_custom_css or "",
                "script_display": "replace",
            }

        if embed_script is not None:
            embed["script"] = embed_script

        validated_data["embed"] = embed
        return validated_data

    def _sync_crm_settings(self, campaign, crm_sync, crm_id, crm_key, sync_schedule):
        if crm_sync:
            sync_campaign, _created = SyncCampaign.objects.get_or_create(
                campaign=campaign,
                defaults={"schedule": sync_schedule or "hourly"},
            )
            sync_campaign.crm_id = crm_id or ""
            sync_campaign.crm_key = crm_key or ""
            if sync_schedule:
                sync_campaign.schedule = sync_schedule
            sync_campaign.save()
            if sync_campaign.has_schedule():
                sync_campaign.start(sync_campaign.schedule)
        else:
            sync_campaign = SyncCampaign.objects.filter(campaign=campaign).first()
            if sync_campaign:
                sync_campaign.crm_id = ""
                sync_campaign.crm_key = ""
                if sync_schedule:
                    sync_campaign.schedule = sync_schedule
                sync_campaign.save()
                sync_campaign.stop()

    def _sync_campaign_status_side_effects(self, campaign):
        if campaign.status_code == 2:
            for schedule_call in ScheduleCall.objects.filter(campaign=campaign, subscribed=True).order_by("id"):
                schedule_call.start_job()
            return

        for schedule_call in ScheduleCall.objects.filter(campaign=campaign, subscribed=True).order_by("id"):
            schedule_call.stop_job()

    @transaction.atomic
    def create(self, validated_data):
        phone_number_ids = validated_data.pop("phone_number_ids", [])
        target_ids = validated_data.pop("target_ids", [])
        crm_sync = validated_data.pop("crm_sync", False)
        crm_id = validated_data.pop("crm_id", "")
        crm_key = validated_data.pop("crm_key", "")
        sync_schedule = validated_data.pop("sync_schedule", "")
        validated_data = self._sync_embed_settings(validated_data)
        campaign = Campaign.objects.create(**validated_data)
        self._sync_phone_numbers(campaign, phone_number_ids)
        self._sync_targets(campaign, target_ids)
        self._sync_crm_settings(campaign, crm_sync, crm_id, crm_key, sync_schedule)
        self._sync_campaign_status_side_effects(campaign)
        return campaign

    @transaction.atomic
    def update(self, instance, validated_data):
        phone_number_ids = validated_data.pop("phone_number_ids", None)
        target_ids = validated_data.pop("target_ids", None)
        crm_sync = validated_data.pop("crm_sync", None)
        crm_id = validated_data.pop("crm_id", "")
        crm_key = validated_data.pop("crm_key", "")
        sync_schedule = validated_data.pop("sync_schedule", "")
        validated_data = self._sync_embed_settings(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._sync_phone_numbers(instance, phone_number_ids)
        self._sync_targets(instance, target_ids)
        if crm_sync is not None:
            self._sync_crm_settings(instance, crm_sync, crm_id, crm_key, sync_schedule)
        self._sync_campaign_status_side_effects(instance)
        return instance
