from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from callpower.apps.api.serializers import (
    CampaignDetailSerializer,
    CampaignSummarySerializer,
    TargetSerializer,
    TwilioPhoneNumberSerializer,
)
from callpower.apps.core.models import (
    Blocklist,
    Call,
    Campaign,
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


class DashboardSummaryApi(APIView):
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


class CampaignListApi(APIView):
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


class CampaignDetailApi(APIView):
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


class CampaignCopyApi(APIView):
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


class PhoneNumberListApi(APIView):
    def get(self, request):
        queryset = TwilioPhoneNumber.objects.order_by("id")
        return Response(
            {
                "count": queryset.count(),
                "results": TwilioPhoneNumberSerializer(queryset, many=True).data,
            }
        )


class TargetListApi(APIView):
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
