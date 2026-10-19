from django.apps import AppConfig


class PublicConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "callpower.apps.public"
    label = "callpower_public"
