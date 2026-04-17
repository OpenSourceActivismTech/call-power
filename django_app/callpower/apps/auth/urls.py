from django.urls import path

from callpower.apps.auth import views


urlpatterns = [
    path("auth/login/", views.login_view, name="auth-login"),
    path("auth/logout/", views.logout_view, name="auth-logout"),
    path("auth/me/", views.me_view, name="auth-me"),
    path("user/login/", views.login_page, name="user-login"),
    path("user/reauth/", views.reauth_page, name="user-reauth"),
    path("user/logout/", views.logout_page, name="user-logout"),
    path("user/create_account", views.create_account_page, name="user-create-account"),
    path("user/change_password", views.change_password_page, name="user-change-password"),
    path("user/reset_password", views.reset_password_page, name="user-reset-password"),
    path("user/profile", views.profile_page, name="user-profile"),
    path("user/<int:user_id>/profile", views.profile_page, name="user-profile-id"),
    path("user/invite", views.invite_page, name="user-invite"),
    path("user/<int:user_id>/remove", views.remove_page, name="user-remove"),
    path("user/lang/", views.language_view, name="user-language"),
    path("admin/user", views.index_page, name="user-index"),
    path("admin/user/<int:user_id>/role", views.role_page, name="user-role"),
]
