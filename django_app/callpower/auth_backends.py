from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from werkzeug.security import check_password_hash

from callpower.apps.core.models import LegacyUser


class LegacyUserBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("login")
        if not login or not password:
            return None

        legacy_user = (
            LegacyUser.objects.filter(name__iexact=login).first()
            or LegacyUser.objects.filter(email__iexact=login).first()
        )
        if not legacy_user:
            return None
        if legacy_user.status_code != 2:
            return None
        if not check_password_hash(legacy_user.password, password):
            return None

        django_user = User.objects.filter(username=f"legacy-{legacy_user.id}").first()
        if not django_user:
            django_user = User(username=f"legacy-{legacy_user.id}")
        django_user.email = legacy_user.email or ""
        django_user.is_active = True
        django_user.is_staff = legacy_user.role_code in (0, 1)
        django_user.is_superuser = legacy_user.role_code == 0
        django_user.set_unusable_password()
        django_user.save()

        if request is not None:
            request.session["legacy_user_id"] = legacy_user.id
            request.session["legacy_role_code"] = legacy_user.role_code
        return django_user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
