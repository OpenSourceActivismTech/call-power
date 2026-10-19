import magic
from flask_wtf import FlaskForm
from flask_babel import gettext as _

from wtforms import (HiddenField, SubmitField, StringField,
                     SelectField, SelectMultipleField,
                     BooleanField, RadioField,
                     FileField, FieldList, FormField)
from wtforms.ext.sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from wtforms_components import IntegerField, read_only
from wtforms_alchemy import PhoneNumberField
from wtforms.widgets import TextArea, Input
from wtforms.validators import Required, Optional, AnyOf, NumberRange, ValidationError, Length
from wtforms_alchemy.validators import Unique

from .constants import (SEGMENT_BY_CHOICES, LOCATION_CHOICES, INCLUDE_SPECIAL_CHOCIES, TARGET_OFFICE_CHOICES, LANGUAGE_CHOICES,
                        CAMPAIGN_STATUS, EMBED_FORM_CHOICES, EMBED_SCRIPT_DISPLAY, LONG_STRING_LEN)

from .models import Campaign, TwilioPhoneNumber

from ..political_data import COUNTRY_CHOICES
from ..sync.constants import SCHEDULE_CHOICES, SCHEDULE_HOURLY
from ..utils import choice_items, choice_keys, choice_values, choice_values_flat


class DisabledSelectField(SelectField):
  def __call__(self, *args, **kwargs):
    kwargs.setdefault('disabled', True)
    return super(DisabledSelectField, self).__call__(*args, **kwargs)


class CountryTypeForm(FlaskForm):
    campaign_country = SelectField(_('Country'), validators=[Required()])
    campaign_type = SelectField(_('Type'), validators=[Required()])
    campaign_language = SelectField(_('Language'), [Required()], choices=LANGUAGE_CHOICES)
    submit = SubmitField(_('Next'))


class TargetForm(FlaskForm):
    order = IntegerField(_('Order'),)
    title = StringField(_('Title'), [Optional()])
    name = StringField(_('Name'), [Required()])
    number = PhoneNumberField(_('Phone Number'), [Required()])
    location = StringField(_('Location'), [Optional()])
    key = StringField(_('Unique Key'), [Optional()])


class CampaignForm(FlaskForm):
    next = HiddenField()
    name = StringField(_('Campaign Name'), [Required(), Length(max=LONG_STRING_LEN), Unique(Campaign.name, message="Campaign with that name already exists")])
    campaign_country = DisabledSelectField(_('Country'), [Optional()], choices=COUNTRY_CHOICES)
    campaign_type = DisabledSelectField(_('Type'), [Optional()])
    campaign_state = SelectField(_('State'), [Optional()])
    campaign_subtype = SelectField(_('Subtype'), [Optional()])
    # nested_type passed to data-field in template, but starts empty

    segment_by = RadioField(_('Segment By'), [Required()], choices=choice_items(SEGMENT_BY_CHOICES),
                            description=True, default=SEGMENT_BY_CHOICES[0][0])
    locate_by = RadioField(_('Locate By'), [Optional()], choices=choice_items(LOCATION_CHOICES),
                           description=True, default=None)
    show_special = BooleanField(_('Include Special Targets'), [Optional()], default=False)
    include_special = SelectField(_('User\'s Representatives'), [Optional()], choices=choice_items(INCLUDE_SPECIAL_CHOCIES),
                           description=True, default=INCLUDE_SPECIAL_CHOCIES[0][0])
    target_set = FieldList(FormField(TargetForm, _('Choose Targets')), validators=[Optional()])
    target_ordering = RadioField(_('Target Order'), [Optional()], description=True)
    target_shuffle_chamber = BooleanField(_('Shuffle within Chamber'), [Optional()], default=True, description=True)
    target_offices = RadioField(_('Target Offices'), [Optional()], choices=choice_items(TARGET_OFFICE_CHOICES),
                            description=True, default=TARGET_OFFICE_CHOICES[0][0])

    call_limit = BooleanField(_('Limit Maximum Calls'), [Optional()], default=False)
    call_maximum = IntegerField(_('Call Maximum'), [Optional(), NumberRange(min=0)])

    phone_number_set = QuerySelectMultipleField(_('Select Phone Numbers'),
                                                query_factory=TwilioPhoneNumber.available_numbers,
                                                description=True, validators=[Required()])
    allow_call_in = BooleanField(_('Allow Call In'))
    allow_intl_calls = BooleanField(_('Allow International Calls'))
    prompt_schedule = BooleanField(_('Prompt to Schedule Recurring Calls'))

    submit = SubmitField(_('Edit Audio'))
    submit_skip_audio = SubmitField(_('Save and Test'))

    def __init__(self, campaign_data, *args, **kwargs):
        super(CampaignForm, self).__init__(*args, **kwargs)

        read_only(self.campaign_country)
        read_only(self.campaign_type)

        self.campaign_type.choices = choice_items(campaign_data.data_provider.campaign_type_choices)
        self.campaign_state.choices = choice_items(campaign_data.region_choices)
        self.campaign_subtype.choices = choice_items(campaign_data.subtype_choices)
        self.target_ordering.choices = choice_items(campaign_data.target_order_choices)

    def validate(self):
        # check default validation
        if not FlaskForm.validate(self):
            return False

        # check nested forms
        for t in self.target_set:
            if not t.form.validate():
                error_fields = ','.join(t.form.errors.keys())
                self.target_set.errors.append({'target': t.name, 'message': 'Invalid target ' + error_fields})
                return False

        return True


class CampaignAudioForm(FlaskForm):
    next = HiddenField()
    msg_intro = StringField(_('Introduction'))
    msg_intro_confirm = StringField(_('Start Confirmation'))
    msg_location = StringField(_('Location Prompt'))
    msg_intro_location = StringField(_('Introduction with Location'))
    msg_invalid_location = StringField(_('Invalid Location'))
    msg_unparsed_location = StringField(_('Unparsed Location'))
    msg_choose_target = StringField(_('Choose Target'))
    msg_prompt_schedule = StringField(_('Prompt to Schedule'))
    msg_alter_schedule = StringField(_('Alter Existing Schedule'))
    msg_schedule_start = StringField(_('Schedule Started'))
    msg_schedule_stop = StringField(_('Schedule Stopped'))
    msg_call_block_intro = StringField(_('Call Block Introduction'))
    msg_target_intro = StringField(_('Target Introduction'))
    msg_target_busy = StringField(_('Target Busy'))
    msg_between_calls = StringField(_('Between Calls'))
    msg_final_thanks = StringField(_('Final Thanks'))
    msg_campaign_complete = StringField(_('Campaign Complete'))

    submit = SubmitField(_('Save and Test'))


class AudioRecordingForm(FlaskForm):
    key = StringField(_('Key'), [Required()])
    file_storage = FileField(_('File'), [Optional()])
    file_type = StringField(_('Type'), [Optional()])
    text_to_speech = FileField(_('Text to Speech'), [Optional()])
    description = StringField(_('Description'), [Optional()])

    def validate_file_storage(form, field):
        if not field.data:
            return True

        # Use Unix libmagic to check the file type. Read just the header
        mime = magic.from_buffer(field.data.read(8192), mime=True)
        if mime in ["audio/wav", "audio/x-wav"] and field.data.mimetype in ["audio/wav", "audio/x-wav"]:
            return True
        if mime in ["audio/mp3", "audio/mpeg"] and field.data.mimetype in ["audio/mp3", "audio/mpeg"]:
            return True
        raise ValidationError("File type must be mp3 or wav, got {}.".format(mime))


class CampaignLaunchForm(FlaskForm):
    next = HiddenField()

    test_call_number = StringField(_('Call Me'))
    test_call_location = StringField(_('Test Location'))
    test_call_country = SelectField(_('Country'), [Optional()], choices=COUNTRY_CHOICES+[('', "Other")])

    # standard embed fields
    embed_script = StringField(_('Display Script'), widget=TextArea(), description=True)
    embed_code = StringField(_('Embed Code'), widget=TextArea(), description=True)
    embed_type = SelectField(_('Form Embed'), [Optional()], choices=choice_items(EMBED_FORM_CHOICES),
        description=True, default=EMBED_FORM_CHOICES[0][0])

    # custom embed fields
    embed_form_sel = StringField(_('Form Selector'))
    embed_phone_sel = StringField(_('Phone Field'))
    embed_location_sel = StringField(_('Location Field'))
    embed_custom_css = StringField(_('Custom CSS URL'))
    embed_script_display = SelectField(_('Script Display'), [Optional()], choices=choice_items(EMBED_SCRIPT_DISPLAY),
        description=True, default=EMBED_SCRIPT_DISPLAY[0][0])
    embed_phone_display = StringField(_('Phone Display'), description=True)
    embed_redirect = StringField(_('Redirect URL'), description=True)
    embed_custom_js = StringField(_('Custom JS Success'), description=True)
    embed_custom_onload = StringField(_('Custom JS Onload'), widget=TextArea(), description=True)

    # CRM sync fields
    crm_sync = BooleanField(_('Sync calls to CRM'), [Optional()], default=False, description=True)
    crm_id = StringField(_('CRM Campaign ID'), description=True)
    crm_key = StringField(_('CRM Campaign Key'), description=True)
    sync_schedule = SelectField(_('Schedule'), choices=choice_items(SCHEDULE_CHOICES), default=SCHEDULE_HOURLY)

    submit = SubmitField(_('Launch'))


class CampaignStatusForm(FlaskForm):
    status_code = RadioField(_("Status"), [AnyOf([str(val) for val in CAMPAIGN_STATUS.keys()])],
                             choices=[(str(val), label) for val, label in CAMPAIGN_STATUS.items()])
    submit = SubmitField(_('Save'))
