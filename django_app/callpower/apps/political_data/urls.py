from django.urls import path

from callpower.apps.political_data import views


urlpatterns = [
    path("search", views.search, name="political-data-search"),
]
