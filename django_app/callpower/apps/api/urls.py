from django.urls import path

from callpower.apps.api.views import (
    CampaignCopyApi,
    CampaignDetailApi,
    CampaignListApi,
    DashboardSummaryApi,
    PhoneNumberListApi,
    TargetListApi,
)


urlpatterns = [
    path("dashboard/summary/", DashboardSummaryApi.as_view(), name="dashboard-summary"),
    path("campaigns/", CampaignListApi.as_view(), name="campaign-list"),
    path("campaigns/<int:campaign_id>/", CampaignDetailApi.as_view(), name="campaign-detail"),
    path("campaigns/<int:campaign_id>/copy/", CampaignCopyApi.as_view(), name="campaign-copy"),
    path("phone-numbers/", PhoneNumberListApi.as_view(), name="phone-number-list"),
    path("targets/", TargetListApi.as_view(), name="target-list"),
]
