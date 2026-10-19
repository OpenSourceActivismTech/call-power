from django import forms

from callpower.apps.core.models import LegacyUser, USER_ROLE, USER_STATUS


PASSWORD_LEN_MIN = 6
PASSWORD_LEN_MAX = 64
USERNAME_LEN_MIN = 4
USERNAME_LEN_MAX = 25


class LoginForm(forms.Form):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)
    login = forms.CharField(label="Username or email")
    password = forms.CharField(
        label="Password",
        min_length=PASSWORD_LEN_MIN,
        max_length=PASSWORD_LEN_MAX,
        widget=forms.PasswordInput,
    )
    remember = forms.BooleanField(label="Remember me", required=False)


class ReauthForm(forms.Form):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)
    password = forms.CharField(
        label="Password",
        min_length=PASSWORD_LEN_MIN,
        max_length=PASSWORD_LEN_MAX,
        widget=forms.PasswordInput,
    )


class CreateUserForm(forms.Form):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)
    email = forms.EmailField(label="Email")
    name = forms.CharField(
        label="Username",
        min_length=USERNAME_LEN_MIN,
        max_length=USERNAME_LEN_MAX,
    )
    phone = forms.CharField(label="Phone Number", required=False, max_length=64)
    password = forms.CharField(
        label="Password",
        min_length=PASSWORD_LEN_MIN,
        max_length=PASSWORD_LEN_MAX,
        widget=forms.PasswordInput,
    )
    password_confirm = forms.CharField(label="Password Confirm", widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", "Passwords don't match")
        return cleaned_data

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        query = LegacyUser.objects.filter(name__iexact=name)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise forms.ValidationError("This username is already registered")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        query = LegacyUser.objects.filter(email__iexact=email)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise forms.ValidationError("This email is already registered")
        return email


class UserForm(forms.Form):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)
    email = forms.EmailField(label="Email")
    name = forms.CharField(
        label="Username",
        min_length=USERNAME_LEN_MIN,
        max_length=USERNAME_LEN_MAX,
    )
    phone = forms.CharField(label="Phone Number", required=False, max_length=64)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        query = LegacyUser.objects.filter(name__iexact=name)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise forms.ValidationError("This username is already registered")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        query = LegacyUser.objects.filter(email__iexact=email)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise forms.ValidationError("This email is already registered")
        return email


class InviteUserForm(forms.Form):
    name = forms.CharField(
        label="Username",
        min_length=USERNAME_LEN_MIN,
        max_length=USERNAME_LEN_MAX,
    )
    email = forms.EmailField(label="Email")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if LegacyUser.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This username is already registered")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if LegacyUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered")
        return email


class RecoverPasswordForm(forms.Form):
    email = forms.EmailField(label="Email")


class ChangePasswordForm(forms.Form):
    email = forms.CharField(widget=forms.HiddenInput(), required=False)
    activation_key = forms.CharField(widget=forms.HiddenInput(), required=False)
    password = forms.CharField(
        label="Password",
        min_length=PASSWORD_LEN_MIN,
        max_length=PASSWORD_LEN_MAX,
        widget=forms.PasswordInput,
    )
    password_confirm = forms.CharField(label="Password Confirm", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", "Passwords don't match")
        return cleaned_data


class UserRoleForm(forms.Form):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)
    role_code = forms.ChoiceField(
        label="Role",
        choices=[(str(value), label) for value, label in USER_ROLE.items()],
    )
    status_code = forms.ChoiceField(
        label="Status",
        choices=[(str(value), label) for value, label in USER_STATUS.items()],
    )

    def clean_role_code(self):
        return int(self.cleaned_data["role_code"])

    def clean_status_code(self):
        return int(self.cleaned_data["status_code"])


class RemoveUserForm(forms.Form):
    username = forms.CharField(widget=forms.HiddenInput)
    confirm_username = forms.CharField(label="Confirm Username")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("username") != cleaned_data.get("confirm_username"):
            self.add_error("confirm_username", "Usernames don't match")
        return cleaned_data


def invitation_initial(user):
    return {
        "email": user.email,
        "name": user.name,
        "phone": user.phone or "",
    }


def profile_initial(user):
    return {
        "email": user.email,
        "name": user.name,
        "phone": user.phone or "",
    }
