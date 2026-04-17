from django.contrib import admin
from django.urls import include, path

from callpower.apps.api.views import AdminAppView


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("callpower.apps.api.urls")),
    path("call/", include("callpower.apps.calls.urls")),
    path("political_data/", include("callpower.apps.political_data.urls")),
    path("admin/", AdminAppView.as_view(), name="admin-app"),
]
