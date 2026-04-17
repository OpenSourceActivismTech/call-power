from django.urls import path

from callpower.apps.api.views import (
    CampaignAudioHideApi,
    CampaignAudioListApi,
    CampaignAudioSelectApi,
    CampaignAudioShowApi,
    CampaignAudioUploadApi,
    CampaignCopyApi,
    CampaignDetailApi,
    CampaignLaunchApi,
    CampaignListApi,
    CampaignTestCallApi,
    DashboardSummaryApi,
    PhoneNumberListApi,
    TargetListApi,
)


urlpatterns = [
    path("dashboard/summary/", DashboardSummaryApi.as_view(), name="dashboard-summary"),
    path("campaigns/", CampaignListApi.as_view(), name="campaign-list"),
    path("campaigns/<int:campaign_id>/", CampaignDetailApi.as_view(), name="campaign-detail"),
    path("campaigns/<int:campaign_id>/copy/", CampaignCopyApi.as_view(), name="campaign-copy"),
    path("campaigns/<int:campaign_id>/audio/", CampaignAudioListApi.as_view(), name="campaign-audio-list"),
    path("campaigns/<int:campaign_id>/audio/upload/", CampaignAudioUploadApi.as_view(), name="campaign-audio-upload"),
    path("campaigns/<int:campaign_id>/audio/<int:recording_id>/select/", CampaignAudioSelectApi.as_view(), name="campaign-audio-select"),
    path("campaigns/<int:campaign_id>/audio/<int:recording_id>/hide/", CampaignAudioHideApi.as_view(), name="campaign-audio-hide"),
    path("campaigns/<int:campaign_id>/audio/<int:recording_id>/show/", CampaignAudioShowApi.as_view(), name="campaign-audio-show"),
    path("campaigns/<int:campaign_id>/launch/", CampaignLaunchApi.as_view(), name="campaign-launch"),
    path("campaigns/<int:campaign_id>/test-call/", CampaignTestCallApi.as_view(), name="campaign-test-call"),
    path("phone-numbers/", PhoneNumberListApi.as_view(), name="phone-number-list"),
    path("targets/", TargetListApi.as_view(), name="target-list"),
]
