# -*- coding: utf-8 -*-

from markupsafe import Markup

from flask_wtf import FlaskForm
from flask_babel import gettext as _
from wtforms import (HiddenField, BooleanField, StringField,
                     PasswordField, SubmitField,
                     RadioField, DateField)
from wtforms.validators import ValidationError, Required, Length, EqualTo, Email, AnyOf
from wtforms_alchemy import PhoneNumberField
from wtforms.fields.html5 import EmailField

from .models import User
from .constants import (PASSWORD_LEN_MIN, PASSWORD_LEN_MAX,
                        USERNAME_LEN_MIN, USERNAME_LEN_MAX,
                        USER_ROLE, USER_STATUS)


class LoginForm(FlaskForm):
    next = HiddenField()
    login = StringField(_('Username or email'), [Required()])
    password = PasswordField(_('Password'), [Required(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    remember = BooleanField(_('Remember me'))
    submit = SubmitField(_('Sign in'))


class UserRoleForm(FlaskForm):
    next = HiddenField()
    role_code = RadioField(_("Role"), [AnyOf([str(val) for val in USER_ROLE.keys()])],
                           choices=[(str(val), label) for val, label in USER_ROLE.items()])
    status_code = RadioField(_("Status"), [AnyOf([str(val) for val in USER_STATUS.keys()])],
                             choices=[(str(val), label) for val, label in USER_STATUS.items()])
    submit = SubmitField(_('Save'))


class CreateUserForm(FlaskForm):
    next = HiddenField()
    email = EmailField(_('Email'), [Required(), Email()])
    name = StringField(_('Username'), [Required(), Length(USERNAME_LEN_MIN, USERNAME_LEN_MAX)])
    phone = PhoneNumberField(_('Phone Number'), description="Optional")
    password = PasswordField(_('Password'), [Required(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    password_confirm = PasswordField(u'Password Confirm', [EqualTo('password', message="Passwords don't match")])
    submit = SubmitField(_('Save'))


class UserForm(FlaskForm):
    next = HiddenField()
    email = EmailField(_('Email'), [Required(), Email()])
    name = StringField(_('Username'), [Required(), Length(USERNAME_LEN_MIN, USERNAME_LEN_MAX)])
    phone = PhoneNumberField(_('Phone Number'), description="Optional")
    submit = SubmitField(_('Save'))


class InviteUserForm(FlaskForm):
    name = StringField(_('Username'), [Required(), Length(USERNAME_LEN_MIN, USERNAME_LEN_MAX)])
    email = EmailField(_('Email'), [Email()])
    submit = SubmitField(_('Send instructions'))

    def validate_name(self, field):
        if User.query.filter_by(name=field.data).first() is not None:
            raise ValidationError(_('This username is already registered'))

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is not None:
            raise ValidationError(_('This email is already registered'))


class RecoverPasswordForm(FlaskForm):
    email = EmailField(_('Email'), [Email()])
    submit = SubmitField(_('Send instructions'))


class RemoveUserForm(FlaskForm):
    username = HiddenField()
    confirm_username = StringField(_('Confirm Username'), [EqualTo('username', message="Usernames don't match")])
    submit = SubmitField('Confirm Removal')


class ChangePasswordForm(FlaskForm):
    email = HiddenField()
    activation_key = HiddenField()
    password = PasswordField(u'Password', [Required(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    password_confirm = PasswordField(u'Password Confirm', [EqualTo('password', message="Passwords don't match")])
    submit = SubmitField('Save')


class ReauthForm(FlaskForm):
    next = HiddenField()
    password = PasswordField(u'Password', [Required(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    submit = SubmitField('Reauthenticate')
