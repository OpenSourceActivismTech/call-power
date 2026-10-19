import json
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from callpower.apps.auth.forms import (
    ChangePasswordForm,
    CreateUserForm,
    InviteUserForm,
    LoginForm,
    RecoverPasswordForm,
    ReauthForm,
    RemoveUserForm,
    UserForm,
    UserRoleForm,
    invitation_initial,
    profile_initial,
)
from callpower.apps.core.models import LegacyUser, USER_ACTIVE, USER_ADMIN, USER_NEW


REAUTH_WINDOW = timedelta(minutes=15)


def _legacy_user_from_request(request):
    legacy_user_id = request.session.get("legacy_user_id")
    if not legacy_user_id:
        return None
    return LegacyUser.objects.filter(pk=legacy_user_id).first()


def _sync_django_user(legacy_user):
    django_user = User.objects.filter(username=f"legacy-{legacy_user.id}").first()
    if not django_user:
        django_user = User(username=f"legacy-{legacy_user.id}")
    django_user.email = legacy_user.email or ""
    django_user.is_active = True
    django_user.is_staff = legacy_user.role_code in (0, 1)
    django_user.is_superuser = legacy_user.role_code == 0
    django_user.set_unusable_password()
    django_user.save()
    return django_user


def _login_legacy_user(request, legacy_user):
    django_user = _sync_django_user(legacy_user)
    request.session["legacy_user_id"] = legacy_user.id
    request.session["legacy_role_code"] = legacy_user.role_code
    login(request, django_user, backend="callpower.auth_backends.LegacyUserBackend")


def _require_legacy_user(request):
    legacy_user = _legacy_user_from_request(request)
    if not request.user.is_authenticated or not legacy_user:
        return None
    return legacy_user


def _require_admin_user(request):
    legacy_user = _require_legacy_user(request)
    if not legacy_user or not legacy_user.is_admin():
        return None
    return legacy_user


def _redirect_to_login(request):
    return redirect(f"{reverse('user-login')}?next={request.get_full_path()}")


def _page_context(request, **extra):
    return {
        "legacy_user": _legacy_user_from_request(request),
        "sitename": settings.SITENAME,
        "admin_email": settings.ADMIN_EMAIL,
        **extra,
    }


@csrf_exempt
@require_POST
def login_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    login_value = (payload.get("login") or "").strip()
    password = payload.get("password") or ""
    if not login_value or not password:
        return JsonResponse({"success": False, "error": "login and password are required"}, status=400)

    user = authenticate(request, username=login_value, password=password)
    if not user:
        return JsonResponse({"success": False, "error": "invalid login"}, status=401)

    login(request, user, backend="callpower.auth_backends.LegacyUserBackend")
    legacy_user = _legacy_user_from_request(request)
    if legacy_user:
        legacy_user.last_accessed = timezone.now()
        legacy_user.save(update_fields=["last_accessed"])

    return JsonResponse(
        {
            "success": True,
            "user": {
                "id": legacy_user.id if legacy_user else None,
                "name": legacy_user.name if legacy_user else user.username,
                "email": legacy_user.email if legacy_user else user.email,
                "role_code": legacy_user.role_code if legacy_user else None,
                "status_code": legacy_user.status_code if legacy_user else None,
            },
        }
    )


@csrf_exempt
@require_POST
def logout_view(request):
    logout(request)
    request.session.flush()
    return JsonResponse({"success": True})


@require_GET
def me_view(request):
    legacy_user = _legacy_user_from_request(request)
    if not request.user.is_authenticated or not legacy_user:
        return JsonResponse({"authenticated": False}, status=401)

    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": legacy_user.id,
                "name": legacy_user.name,
                "email": legacy_user.email,
                "role_code": legacy_user.role_code,
                "status_code": legacy_user.status_code,
            },
        }
    )


def login_page(request):
    if _require_legacy_user(request):
        return redirect("admin-app")

    form = LoginForm(
        request.POST or None,
        initial={
            "login": request.GET.get("login", ""),
            "next": request.GET.get("next", ""),
        },
    )

    if request.method == "POST" and form.is_valid():
        login_value = form.cleaned_data["login"]
        password = form.cleaned_data["password"]
        user = authenticate(request, username=login_value, password=password)
        legacy_user = _legacy_user_from_request(request)
        if user and legacy_user:
            login(request, user, backend="callpower.auth_backends.LegacyUserBackend")
            legacy_user.last_accessed = timezone.now()
            legacy_user.save(update_fields=["last_accessed"])
            if form.cleaned_data["remember"]:
                request.session.set_expiry(60 * 60 * 24 * 14)
            messages.success(request, "Logged in")
            return redirect(form.cleaned_data["next"] or reverse("admin-app"))
        messages.warning(request, "Sorry, invalid login")

    return render(request, "account/login.html", _page_context(request, form=form))


def reauth_page(request):
    legacy_user = _require_legacy_user(request)
    if not legacy_user:
        return _redirect_to_login(request)

    form = ReauthForm(
        request.POST or None,
        initial={"next": request.GET.get("next", "")},
    )
    if request.method == "POST" and form.is_valid():
        if legacy_user.check_password(form.cleaned_data["password"]):
            request.session["legacy_reauth_at"] = timezone.now().isoformat()
            messages.success(request, "Reauthenticated.")
            return redirect(form.cleaned_data["next"] or reverse("user-change-password"))
        messages.warning(request, "Password is incorrect.")

    return render(request, "account/reauth.html", _page_context(request, form=form))


def logout_page(request):
    if request.method == "POST":
        logout(request)
        request.session.flush()
        messages.success(request, "Logged out")
        return redirect("site-index")
    return render(request, "account/logout.html", _page_context(request))


def create_account_page(request):
    activation_key = request.GET.get("activation_key") or request.POST.get("activation_key")
    email = request.GET.get("email") or request.POST.get("email")
    legacy_user = (
        LegacyUser.objects.filter(activation_key=activation_key, email=email).first()
        if activation_key and email
        else None
    )
    if legacy_user is None:
        return render(request, "account/invalid_invitation.html", _page_context(request), status=404)

    form = CreateUserForm(
        request.POST or None,
        user=legacy_user,
        initial={
            **invitation_initial(legacy_user),
            "next": request.GET.get("next", ""),
        },
    )
    if request.method == "POST" and form.is_valid():
        legacy_user.email = form.cleaned_data["email"]
        legacy_user.name = form.cleaned_data["name"]
        legacy_user.phone = form.cleaned_data["phone"]
        legacy_user.set_password(form.cleaned_data["password"])
        legacy_user.status_code = USER_ACTIVE
        legacy_user.last_accessed = timezone.now()
        legacy_user.activation_key = None
        legacy_user.save(
            update_fields=[
                "email",
                "name",
                "phone",
                "password",
                "status_code",
                "last_accessed",
                "activation_key",
            ]
        )
        _login_legacy_user(request, legacy_user)
        messages.success(request, "Your account is ready.")
        return redirect(form.cleaned_data["next"] or reverse("admin-app"))

    return render(request, "account/create_account.html", _page_context(request, form=form))


def _resolve_change_password_user(request):
    legacy_user = _require_legacy_user(request)
    if legacy_user:
        reauth_at = request.session.get("legacy_reauth_at")
        if reauth_at:
            try:
                reauth_time = timezone.datetime.fromisoformat(reauth_at)
                if timezone.is_naive(reauth_time):
                    reauth_time = timezone.make_aware(reauth_time, timezone.get_current_timezone())
            except ValueError:
                reauth_time = None
            if reauth_time and timezone.now() - reauth_time <= REAUTH_WINDOW:
                return legacy_user, None
        return None, redirect(f"{reverse('user-reauth')}?next={reverse('user-change-password')}")

    activation_key = request.GET.get("activation_key") or request.POST.get("activation_key")
    email = request.GET.get("email") or request.POST.get("email")
    if not activation_key or not email:
        return None, None
    return LegacyUser.objects.filter(activation_key=activation_key, email=email).first(), None


def change_password_page(request):
    legacy_user, redirect_response = _resolve_change_password_user(request)
    if redirect_response:
        return redirect_response
    if legacy_user is None:
        return render(request, "account/forbidden.html", _page_context(request), status=403)

    form = ChangePasswordForm(
        request.POST or None,
        initial={"email": legacy_user.email, "activation_key": legacy_user.activation_key or ""},
    )
    if request.method == "POST" and form.is_valid():
        legacy_user.set_password(form.cleaned_data["password"])
        legacy_user.activation_key = None
        legacy_user.save(update_fields=["password", "activation_key"])
        request.session.pop("legacy_reauth_at", None)
        logout(request)
        request.session.flush()
        messages.success(request, "Your password has been changed, please log in again")
        return redirect("user-login")

    return render(
        request,
        "account/change_password.html",
        _page_context(request, legacy_user_record=legacy_user, form=form),
    )


def reset_password_page(request):
    form = RecoverPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        messages.success(
            request,
            "If that address is associated with an account you'll receive a password reset email shortly.",
        )
        legacy_user = LegacyUser.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        if legacy_user:
            legacy_user.activation_key = str(uuid4())
            legacy_user.save(update_fields=["activation_key"])
            url = request.build_absolute_uri(
                reverse("user-change-password")
                + f"?email={legacy_user.email}&activation_key={legacy_user.activation_key}"
            )
            body = render_to_string(
                "account/email/reset_password.txt",
                {
                    "sitename": settings.SITENAME,
                    "username": legacy_user.name,
                    "url": url,
                },
            )
            send_mail(
                subject=f"Reset your password for {settings.SITENAME}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[legacy_user.email],
                fail_silently=False,
            )
        return redirect("user-reset-password")

    return render(request, "account/reset_password.html", _page_context(request, form=form))


def profile_page(request, user_id=None):
    legacy_user = _require_legacy_user(request)
    if not legacy_user:
        return _redirect_to_login(request)

    target_user = get_object_or_404(LegacyUser, pk=user_id) if user_id else legacy_user
    if target_user.pk != legacy_user.pk and not legacy_user.is_admin():
        return render(request, "account/forbidden.html", _page_context(request), status=403)

    form = UserForm(request.POST or None, user=target_user, initial=profile_initial(target_user))
    if request.method == "POST" and form.is_valid():
        target_user.email = form.cleaned_data["email"]
        target_user.name = form.cleaned_data["name"]
        target_user.phone = form.cleaned_data["phone"]
        target_user.save(update_fields=["email", "name", "phone"])
        _sync_django_user(target_user)
        messages.success(request, "User profile updated.")
        return redirect(reverse("user-profile-id", args=[target_user.id]) if user_id else reverse("user-profile"))

    return render(
        request,
        "account/profile.html",
        _page_context(request, target_user=target_user, form=form),
    )


def invite_page(request):
    legacy_user = _require_admin_user(request)
    if not legacy_user:
        return _redirect_to_login(request) if not _require_legacy_user(request) else render(
            request, "account/forbidden.html", _page_context(request), status=403
        )

    form = InviteUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invitee = LegacyUser(
            name=form.cleaned_data["name"],
            email=form.cleaned_data["email"],
            activation_key=str(uuid4()),
            status_code=USER_NEW,
            role_code=legacy_user.role_code if legacy_user.role_code != USER_ADMIN else 1,
            created_time=timezone.now(),
        )
        invitee.set_password(invitee.activation_key)
        invitee.save()

        url = request.build_absolute_uri(
            reverse("user-create-account")
            + f"?email={invitee.email}&activation_key={invitee.activation_key}"
        )
        body = render_to_string(
            "account/email/invite_user.txt",
            {
                "sitename": settings.SITENAME,
                "username": invitee.name,
                "url": url,
            },
        )
        send_mail(
            subject=f"Create account on {settings.SITENAME}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitee.email],
            fail_silently=False,
        )
        messages.success(request, f"Invited {invitee.email}")
        return redirect("user-index")

    return render(request, "account/invite.html", _page_context(request, form=form))


def index_page(request):
    legacy_user = _require_admin_user(request)
    if not legacy_user:
        return _redirect_to_login(request) if not _require_legacy_user(request) else render(
            request, "account/forbidden.html", _page_context(request), status=403
        )
    users = LegacyUser.objects.order_by("name", "id")
    return render(request, "account/list.html", _page_context(request, users=users))


def role_page(request, user_id):
    legacy_user = _require_admin_user(request)
    if not legacy_user:
        return _redirect_to_login(request) if not _require_legacy_user(request) else render(
            request, "account/forbidden.html", _page_context(request), status=403
        )
    target_user = get_object_or_404(LegacyUser, pk=user_id)
    form = UserRoleForm(
        request.POST or None,
        initial={
            "role_code": str(target_user.role_code),
            "status_code": str(target_user.status_code),
            "next": request.GET.get("next", ""),
        },
    )
    if request.method == "POST" and form.is_valid():
        if target_user.pk == legacy_user.pk and target_user.role_code == USER_ADMIN and form.cleaned_data["role_code"] > USER_ADMIN:
            messages.warning(request, "Cannot remove your own admin role.")
        else:
            target_user.role_code = form.cleaned_data["role_code"]
            target_user.status_code = form.cleaned_data["status_code"]
            target_user.save(update_fields=["role_code", "status_code"])
            _sync_django_user(target_user)
            messages.success(request, f"Updated {target_user.email}.")
            return redirect(form.cleaned_data["next"] or reverse("user-index"))

    return render(request, "account/role.html", _page_context(request, target_user=target_user, form=form))


def remove_page(request, user_id):
    legacy_user = _require_admin_user(request)
    if not legacy_user:
        return _redirect_to_login(request) if not _require_legacy_user(request) else render(
            request, "account/forbidden.html", _page_context(request), status=403
        )
    target_user = get_object_or_404(LegacyUser, pk=user_id)
    if target_user.pk == legacy_user.pk:
        messages.warning(request, "Cannot remove your own account.")
        return redirect("user-index")

    form = RemoveUserForm(request.POST or None, initial={"username": target_user.name})
    if request.method == "POST" and form.is_valid():
        User.objects.filter(username=f"legacy-{target_user.id}").delete()
        target_user.delete()
        messages.success(request, f"Removed {target_user.email}.")
        return redirect("user-index")

    return render(request, "account/remove.html", _page_context(request, target_user=target_user, form=form))


@require_POST
def language_view(request):
    language_code = (request.POST.get("lang") or request.POST.get("language") or "").strip()
    if language_code:
        request.session["django_language"] = language_code
    return JsonResponse({"success": True, "language": language_code})
