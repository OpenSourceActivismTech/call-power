from django.urls import path

from callpower.apps.public import views


urlpatterns = [
    path("", views.index, name="site-index"),
    path("create", views.legacy_call_redirect, name="site-create"),
    path("incoming_call", views.legacy_call_incoming, name="site-incoming-call"),
    path("call_complete_status", views.legacy_call_status, name="site-call-complete-status"),
    path("campaign/<int:campaign_id>/", views.campaign_page, name="public-campaign-page"),
    path("api/campaign/<int:campaign_id>/embed.js", views.campaign_embed_js, name="campaign-embed-js"),
    path(
        "api/campaign/<int:campaign_id>/CallPowerForm.js",
        views.campaign_form_js,
        name="campaign-form-js",
    ),
    path(
        "api/campaign/<int:campaign_id>/embed_iframe.html",
        views.campaign_embed_iframe,
        name="campaign-embed-iframe",
    ),
    path(
        "api/campaign/<int:campaign_id>/embed_code.html",
        views.campaign_embed_code,
        name="campaign-embed-code",
    ),
    path("api/campaign/<int:campaign_id>/count.json", views.campaign_count, name="campaign-count"),
]
