import os
import json

from django.conf import settings
from django.core.files.storage import default_storage
from django.test import RequestFactory
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from callpower.apps.api.serializers import (
    CampaignAudioRecordingSerializer,
    CampaignDetailSerializer,
    CampaignSummarySerializer,
    TargetSerializer,
    TwilioPhoneNumberSerializer,
)
from callpower.apps.calls.views import create as create_call_view
from callpower.apps.core.models import (
    AudioRecording,
    Blocklist,
    Call,
    Campaign,
    CampaignAudioRecording,
    CampaignPhoneNumber,
    CampaignTarget,
    LegacyUser,
    ScheduleCall,
    Target,
    TwilioPhoneNumber,
)


class AdminAppView(TemplateView):
    template_name = "admin_app.html"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "debug": settings.DEBUG,
                "react_dev_server_url": settings.REACT_DEV_SERVER_URL.rstrip("/"),
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthenticatedAPIView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_authenticated or not request.session.get("legacy_user_id"):
            raise NotAuthenticated("Authentication required")


class DashboardSummaryApi(AuthenticatedAPIView):
    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        payload = {
            "campaigns": Campaign.objects.count(),
            "completed_calls_this_month": Call.objects.filter(
                status="completed",
                timestamp__gte=month_start,
            ).count(),
            "scheduled_calls": ScheduleCall.objects.filter(subscribed=True).count(),
            "active_blocks": sum(1 for block in Blocklist.objects.all() if block.is_active()),
            "users": LegacyUser.objects.count(),
        }
        return Response(payload)


class CampaignListApi(AuthenticatedAPIView):
    def get(self, request):
        queryset = Campaign.with_dashboard_counts()

        status_code = request.query_params.get("status_code")
        if status_code not in (None, ""):
            queryset = queryset.filter(status_code=status_code)

        search = request.query_params.get("q")
        if search:
            queryset = queryset.filter(name__icontains=search)

        queryset = queryset.annotate(
            active_scheduled_calls=Count(
                "scheduled_calls",
                filter=Q(scheduled_calls__subscribed=True),
                distinct=True,
            )
        )[:50]

        data = CampaignSummarySerializer(queryset, many=True).data
        for item, campaign in zip(data, queryset):
            item["active_scheduled_calls"] = getattr(campaign, "active_scheduled_calls", 0)
        return Response({"count": len(data), "results": data})

    def post(self, request):
        serializer = CampaignDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        return Response(
            CampaignDetailSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )


class CampaignDetailApi(AuthenticatedAPIView):
    def get_object(self, campaign_id):
        return Campaign.objects.get(pk=campaign_id)

    def get(self, request, campaign_id):
        campaign = self.get_object(campaign_id)
        return Response(CampaignDetailSerializer(campaign).data)

    def patch(self, request, campaign_id):
        campaign = self.get_object(campaign_id)
        serializer = CampaignDetailSerializer(
            campaign,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        return Response(CampaignDetailSerializer(campaign).data)


class CampaignCopyApi(AuthenticatedAPIView):
    @transaction.atomic
    def post(self, request, campaign_id):
        source = Campaign.objects.get(pk=campaign_id)
        copy_campaign = Campaign.objects.create(
            name=f"{source.name} (copy)",
            country_code=source.country_code,
            campaign_type=source.campaign_type,
            campaign_state=source.campaign_state,
            campaign_subtype=source.campaign_subtype,
            campaign_language=source.campaign_language,
            segment_by=source.segment_by,
            locate_by=source.locate_by,
            include_special=source.include_special,
            target_ordering=source.target_ordering,
            target_shuffle_chamber=source.target_shuffle_chamber,
            target_offices=source.target_offices,
            call_maximum=source.call_maximum,
            allow_call_in=source.allow_call_in,
            allow_intl_calls=source.allow_intl_calls,
            prompt_schedule=source.prompt_schedule,
            status_code=source.status_code,
            embed=source.embed,
        )

        for link in source.campaign_phone_links.all():
            CampaignPhoneNumber.objects.create(
                campaign=copy_campaign,
                phone_id=link.phone_id,
            )

        for link in source.campaign_target_links.order_by("order", "id").all():
            CampaignTarget.objects.create(
                campaign=copy_campaign,
                target_id=link.target_id,
                order=link.order,
            )

        return Response(
            CampaignDetailSerializer(copy_campaign).data,
            status=status.HTTP_201_CREATED,
        )


class PhoneNumberListApi(AuthenticatedAPIView):
    def get(self, request):
        queryset = TwilioPhoneNumber.objects.order_by("id")
        return Response(
            {
                "count": queryset.count(),
                "results": TwilioPhoneNumberSerializer(queryset, many=True).data,
            }
        )


class TargetListApi(AuthenticatedAPIView):
    def get(self, request):
        queryset = Target.objects.order_by("name", "id")
        search = request.query_params.get("q")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(title__icontains=search)
                | Q(location__icontains=search)
                | Q(key__icontains=search)
            )
        queryset = queryset[:100]
        return Response(
            {
                "count": len(queryset),
                "results": TargetSerializer(queryset, many=True).data,
            }
        )


class CampaignAudioListApi(AuthenticatedAPIView):
    def get(self, request, campaign_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        queryset = (
            AudioRecording.objects.filter(campaign_audio_recordings__campaign=campaign)
            .distinct()
            .order_by("key", "-version", "-id")
        )
        key = request.query_params.get("key")
        if key:
            queryset = queryset.filter(key=key)
        return Response(
            {
                "count": queryset.count(),
                "results": CampaignAudioRecordingSerializer(
                    queryset,
                    many=True,
                    context={"campaign": campaign},
                ).data,
            }
        )


class CampaignAudioUploadApi(AuthenticatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def _validate_upload(self, uploaded_file):
        if not uploaded_file:
            return None

        allowed_content_types = {
            "audio/wav",
            "audio/x-wav",
            "audio/mpeg",
            "audio/mp3",
        }
        extension = os.path.splitext(uploaded_file.name)[1].lower()
        if uploaded_file.content_type not in allowed_content_types and extension not in {".wav", ".mp3"}:
            raise ValueError(f"File type must be mp3 or wav, got {uploaded_file.content_type or extension}.")
        return extension.lstrip(".") or "mp3"

    @transaction.atomic
    def post(self, request, campaign_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        message_key = (request.data.get("key") or "").strip()
        description = (request.data.get("description") or "").strip()
        text_to_speech = (request.data.get("text_to_speech") or "").strip()
        uploaded_file = request.FILES.get("file_storage")

        if not message_key:
            return Response({"success": False, "errors": {"key": ["This field is required."]}}, status=400)
        if not uploaded_file and not text_to_speech:
            return Response(
                {"success": False, "errors": {"file_storage": ["Upload a file or provide text_to_speech."]}},
                status=400,
            )

        try:
            extension = self._validate_upload(uploaded_file)
        except ValueError as exc:
            return Response({"success": False, "errors": {"file_storage": [str(exc)]}}, status=400)

        last_version = (
            AudioRecording.objects.filter(key=message_key).order_by("-version").values_list("version", flat=True).first()
        )
        version = int(last_version or 0) + 1

        stored_name = ""
        if uploaded_file:
            stored_name = default_storage.save(
                f"audio/campaign_{campaign.id}_{message_key}_{version}.{extension}",
                uploaded_file,
            )

        recording = AudioRecording.objects.create(
            key=message_key,
            file_storage=stored_name or "",
            text_to_speech="" if uploaded_file else text_to_speech,
            version=version,
            description=description,
            hidden=False,
        )

        CampaignAudioRecording.objects.filter(
            campaign=campaign,
            recording__key=message_key,
        ).update(selected=False)

        CampaignAudioRecording.objects.update_or_create(
            campaign=campaign,
            recording=recording,
            defaults={"selected": True},
        )

        return Response(
            {
                "success": True,
                "message": "Audio recording uploaded",
                "key": message_key,
                "version": version,
                "recording": CampaignAudioRecordingSerializer(
                    recording,
                    context={"campaign": campaign},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CampaignAudioSelectApi(AuthenticatedAPIView):
    @transaction.atomic
    def post(self, request, campaign_id, recording_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        recording = AudioRecording.objects.get(pk=recording_id)

        CampaignAudioRecording.objects.filter(
            campaign=campaign,
            recording__key=recording.key,
        ).update(selected=False)

        CampaignAudioRecording.objects.update_or_create(
            campaign=campaign,
            recording=recording,
            defaults={"selected": True},
        )

        return Response(
            {
                "success": True,
                "message": "Audio recording selected",
                "key": recording.key,
                "version": recording.version,
                "recording": CampaignAudioRecordingSerializer(
                    recording,
                    context={"campaign": campaign},
                ).data,
            }
        )


class CampaignAudioHideApi(AuthenticatedAPIView):
    @transaction.atomic
    def post(self, request, campaign_id, recording_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        recording = AudioRecording.objects.get(pk=recording_id)
        recording.hidden = True
        recording.save(update_fields=["hidden"])
        CampaignAudioRecording.objects.filter(campaign=campaign, recording=recording).update(selected=False)
        return Response(
            {
                "success": True,
                "message": "Audio recording hidden",
                "key": recording.key,
                "version": recording.version,
                "recording": CampaignAudioRecordingSerializer(
                    recording,
                    context={"campaign": campaign},
                ).data,
            }
        )


class CampaignAudioShowApi(AuthenticatedAPIView):
    def post(self, request, campaign_id, recording_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        recording = AudioRecording.objects.get(pk=recording_id)
        recording.hidden = False
        recording.save(update_fields=["hidden"])
        return Response(
            {
                "success": True,
                "message": "Audio recording visible",
                "key": recording.key,
                "version": recording.version,
                "recording": CampaignAudioRecordingSerializer(
                    recording,
                    context={"campaign": campaign},
                ).data,
            }
        )


class CampaignLaunchApi(AuthenticatedAPIView):
    def post(self, request, campaign_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        campaign.status_code = 2
        campaign.save(update_fields=["status_code"])
        return Response(
            {
                "success": True,
                "message": "Campaign launched",
                "campaign": CampaignDetailSerializer(campaign).data,
            }
        )


class CampaignTestCallApi(AuthenticatedAPIView):
    def post(self, request, campaign_id):
        campaign = Campaign.objects.get(pk=campaign_id)
        payload = request.data
        phone = (payload.get("userPhone") or "").strip()
        location = (payload.get("userLocation") or "").strip()
        country = (payload.get("userCountry") or campaign.country_code or "US").strip()
        record = payload.get("record")

        if not phone:
            return Response(
                {"success": False, "error": "userPhone is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        factory = RequestFactory()
        internal_request = factory.post(
            "/call/create",
            data={
                "campaignId": str(campaign.id),
                "userPhone": phone,
                "userLocation": location,
                "userCountry": country,
                "record": record or "",
            },
        )
        internal_request.META["REMOTE_ADDR"] = request.META.get("REMOTE_ADDR", "127.0.0.1")
        response = create_call_view(internal_request)
        payload = json.loads(response.content.decode("utf-8"))
        return Response(payload, status=response.status_code)
