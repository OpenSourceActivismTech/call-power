from django.urls import path

from callpower.apps.calls import views


urlpatterns = [
    path("create", views.create, name="call-create"),
    path("incoming", views.incoming, name="call-incoming"),
    path("connection", views.connection, name="call-connection"),
    path("location_parse", views.location_parse, name="call-location-parse"),
    path("make_calls", views.make_calls, name="call-make-calls"),
    path("make_single", views.make_single, name="call-make-single"),
    path("complete", views.complete, name="call-complete"),
    path("status_callback", views.status_callback, name="call-status-callback"),
    path("status_inbound", views.status_inbound, name="call-status-inbound"),
]
