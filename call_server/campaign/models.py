from datetime import datetime

from flask import current_app, url_for
from sqlalchemy_utils.types import phone_number, JSONType
from flask_store.sqla import FlaskStoreType
from sqlalchemy import UniqueConstraint

from ..extensions import db, cache
from ..political_data import get_country_data, check_political_data_cache
from .constants import (STRING_LEN, LONG_STRING_LEN, TWILIO_SID_LENGTH, LANGUAGE_CHOICES,
                        CAMPAIGN_STATUS, STATUS_PAUSED,
                        SEGMENT_BY_CHOICES, LOCATION_CHOICES, INCLUDE_SPECIAL_CHOCIES, TARGET_OFFICE_CHOICES)


class Campaign(db.Model):
    __tablename__ = 'campaign_campaign'

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime, default=datetime.now)

    name = db.Column(db.String(LONG_STRING_LEN), nullable=False, unique=True)
    country_code = db.Column(db.String(STRING_LEN), index=True)
    campaign_type = db.Column(db.String(STRING_LEN))
    campaign_state = db.Column(db.String(STRING_LEN))
    campaign_subtype = db.Column(db.String(STRING_LEN))
    campaign_language = db.Column(db.String(STRING_LEN))

    segment_by = db.Column(db.String(STRING_LEN))
    locate_by = db.Column(db.String(STRING_LEN))
    include_special = db.Column(db.String(STRING_LEN))
    target_set = db.relationship('Target', secondary='campaign_target_sets',
                                 order_by='campaign_target_sets.c.order')
    target_ordering = db.Column(db.String(STRING_LEN))
    target_shuffle_chamber = db.Column(db.Boolean, default=True)
    target_offices = db.Column(db.String(STRING_LEN))
    call_maximum = db.Column(db.SmallInteger, nullable=True)
    allow_call_in = db.Column(db.Boolean, default=False)
    allow_intl_calls = db.Column(db.Boolean, default=False)
    
    phone_number_set = db.relationship('TwilioPhoneNumber', secondary='campaign_phone_numbers')
    prompt_schedule = db.Column(db.Boolean, default=False)
    audio_recordings = db.relationship('AudioRecording', secondary='campaign_audio_recordings')

    status_code = db.Column(db.SmallInteger, default=STATUS_PAUSED)

    embed = db.Column(JSONType)

    @property
    def status(self):
        return CAMPAIGN_STATUS.get(self.status_code, '')

    def __str__(self):
        return self.name

    def audio(self, key):
        return self.audio_or_default(key)[0]

    def has_audio(self, key='msg_intro'):
        # returns True if the campaign has non-default audio defined
        # False if not
        return not self.audio_or_default(key)[1]

    def audio_or_default(self, key):
        """Convenience method for getting selected audio recordings for this campaign by key.
        Returns tuple (audio recording or default message, is default message) """
        campaignAudio = self._audio_query().filter(
            CampaignAudioRecording.recording.has(key=key)
        ).first()

        if campaignAudio:
            return (campaignAudio.recording, False)
        else:
            # if not defined by user, return default
            return (current_app.config.CAMPAIGN_MESSAGE_DEFAULTS.get(key), True)

    def audio_msgs(self):
        "Convenience method for getting all selected audio recordings for this campaign"
        table = {}
        for r in self._audio_query().all():
            if r.recording.text_to_speech:
                table[r.recording.key] = r.recording.text_to_speech
            else:
                table[r.recording.key] = r.recording.file_url()
        return table

    def _audio_query(self):
        return CampaignAudioRecording.query.filter(
            CampaignAudioRecording.campaign_id == self.id,
            CampaignAudioRecording.selected == True)

    def campaign_type_display(self):
        "Display method for this campaign's type"
        campaign_data = self.get_campaign_data()
        if campaign_data:
            return campaign_data.type_name
        else:
            return None

    def campaign_subtype_display(self):
        "Display method for this campaign's subtype"
        campaign_data = self.get_campaign_data()
        if campaign_data:
            return campaign_data.get_subtype_display(self.campaign_subtype, campaign_region=self.campaign_state)
        else:
            return None

    @property
    def language_code(self):
        if self.campaign_language and self.country_code:
            return u"{}-{}".format(self.campaign_language.lower(), self.country_code.upper())
        else:
            return u"en-US"

    def language_display(self):
        return dict(LANGUAGE_CHOICES).get(self.campaign_language, '?')

    def order_display(self):
        "Display method for this campaign's ordering"
        campaign_data = self.get_campaign_data()
        if campaign_data:
            return campaign_data.get_order_display(self.target_ordering)
        else:
            return None

    def include_special_display(self):
        "Display method for this campaign's special inclusion"
        return dict(INCLUDE_SPECIAL_CHOCIES).get(self.include_special, '?')

    def phone_numbers(self, region_code=None):
        "Phone numbers for this campaign, can be limited to a specified region code (ISO-2)"
        if region_code and not self.allow_intl_calls:
            # convert region_code to country_code for comparison
            country_code = phone_number.phonenumbers.country_code_for_region(region_code.upper())
            return [n.number.e164 for n in self.phone_number_set if n.number.country_code == country_code]
        else:
            # return all numbers in set
            return [n.number.e164 for n in self.phone_number_set]

    def required_fields(self):
        """API convenience method for rendering campaigns externally
        Returns dict of parameters and data types required to place call"""
        fields = dict()
        fields['userPhone'] = self.country_code
        if self.segment_by == 'location':
            fields['userLocation'] = self.locate_by
        return fields

    def segment_display(self):
        "Display method for this campaign's segmenting and locating of callers"
        val = dict(SEGMENT_BY_CHOICES).get(self.segment_by, '')
        if self.segment_by == 'location':
            val = '%s - %s' % (val, dict(LOCATION_CHOICES).get(self.locate_by))
        return val

    def targets(self):
        "Convenience method for getting list of target names and phone numbers"
        return [(t.name, t.number.e164) for t in self.target_set]

    def targets_display(self):
        "Display method for this campaign's target list if specified, or subtype (like Congress - Senate)"
        if self.target_set:
            target_strings = []
            for t in self.target_set:
                if t.location:
                    target_strings.append("%s (%s)" % (t.name, t.location))
                else:
                    target_strings.append("%s" % t.name)
            return ", ".join(target_strings)
        else:
            return self.campaign_subtype_display()

    def target_offices_display(self):
        "Display method for this campaign's target offices"
        val = dict(TARGET_OFFICE_CHOICES).get(self.target_offices, '')
        return val

    def scheduled_calls_subscribers(self):
        "Number of scheduled calls for this campaign where subscribed = True"
        return self.scheduled_call_subscribed.filter_by(subscribed=True)

    @staticmethod
    def get_campaign_type_choices(country_code, cache=cache):
        country_data = get_country_data(country_code, cache=cache, api_cache='localmem')
        return country_data.campaign_type_choices

    def get_country_data(self, cache=cache):
        return get_country_data(self.country_code, cache=cache, api_cache='localmem')

    def get_campaign_data(self, cache=cache):
        country_data = self.get_country_data(cache)
        return country_data.get_campaign_type(self.campaign_type)


class CampaignTarget(db.Model):
    __tablename__ = 'campaign_target_sets'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign_campaign.id'))
    target_id = db.Column(db.Integer, db.ForeignKey('campaign_target.id'))
    order = db.Column(db.Integer())

    campaign = db.relationship('Campaign', lazy='joined')
    target = db.relationship('Target', lazy='joined')


class CampaignPhoneNumber(db.Model):
    __tablename__ = 'campaign_phone_numbers'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign_campaign.id'))
    phone_id = db.Column(db.Integer, db.ForeignKey('campaign_phone.id'), unique=False)


class Target(db.Model):
    __tablename__ = 'campaign_target'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(STRING_LEN), index=True, nullable=True)  # like us:bioguide:S000148
    title = db.Column(db.String(STRING_LEN), nullable=True)
    name = db.Column(db.String(STRING_LEN), nullable=False, unique=False)
    district = db.Column(db.String(STRING_LEN), nullable=True)
    number = db.Column(phone_number.PhoneNumberType(max_length=23)) # increase from default of 20 to allow for 5 digit extensions 
    location = db.Column(db.String(STRING_LEN), nullable=True, unique=False)
    offices = db.relationship('TargetOffice', backref="target")

    def __str__(self):
        return self.key

    def full_name(self):
        return u'{} {}'.format(self.title, self.name)

    def phone_number(self):
        return self.number.e164

    @classmethod
    def get_or_create(cls, uid, prefix=None, update_offices=True, commit=True, cache=cache):
        if prefix:
            key = '%s:%s' % (prefix, uid)
        else:
            key = uid
        t = Target.query.filter(Target.key == key) \
            .order_by(Target.id.desc()).first()
        created = False

        data = check_political_data_cache(key, cache)
        offices = data.pop('offices')
        if 'uid' in data:
            del data['uid']

        if not t:
            # create target object
            t = Target(**data)
            t.key = key # specify this directly to ensure it saves
            db.session.add(t)
            created = True
        elif data:
            if t.key == data.get('key'):
                # check for updated data, only on full cache key match
                check_attrs = ['location', 'number']
                for a in check_attrs:
                    new_val = data.get(a)
                    if new_val and getattr(t, a) != new_val:
                        setattr(t, a, new_val)
                        created = True
        
        if offices and update_offices:
            existing_target_office_uids = [o.uid for o in t.offices]
            # need to check against existing offices, because the underlying data may have been updated

            for office in offices:
                if office.get('uid') in existing_target_office_uids:
                    # existing office, check to update the location and type
                    o = TargetOffice.query.filter_by(target_id=t.id, uid=office.get('uid')).first()
                    check_attrs = ['name', 'type', 'address', 'number']
                    for a in check_attrs:
                        if getattr(o, a) != office.get(a):
                            setattr(o, a, office.get(a))
                            db.session.add(o)
                            created = True
                else:
                     # create new office object, link to target
                    o = TargetOffice(**office)
                    o.target = t
                    db.session.add(o)
                    created = True

        if created and commit:
            # save to db
            db.session.commit()

        return t, created


class TargetOffice(db.Model):
    __tablename__ = 'campaign_target_office'

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(STRING_LEN), index=True, nullable=True)  # for US, this is bioguide_id-location_name
    name = db.Column(db.String(STRING_LEN), nullable=True)
    address = db.Column(db.String(STRING_LEN), nullable=True, unique=False)
    latlon = db.Column(db.String(STRING_LEN), nullable=True, unique=False)
    type = db.Column(db.String(STRING_LEN), nullable=True, unique=False)
    number = db.Column(phone_number.PhoneNumberType(max_length=23)) # increase from default of 20 to allow for 5 digit extensions 
    target_id = db.Column(db.Integer, db.ForeignKey('campaign_target.id'))

    def __str__(self):
        return u"{} {}".format(self.target, self.type)

    def phone_number(self):
        return self.number.e164

class TwilioPhoneNumber(db.Model):
    __tablename__ = 'campaign_phone'

    id = db.Column(db.Integer, primary_key=True)
    twilio_sid = db.Column(db.String(TWILIO_SID_LENGTH))
    twilio_app = db.Column(db.String(TWILIO_SID_LENGTH))
    call_in_allowed = db.Column(db.Boolean, default=False)
    call_in_campaign_id = db.Column(db.Integer, db.ForeignKey('campaign_campaign.id'))
    number = db.Column(phone_number.PhoneNumberType())

    call_in_campaign = db.relationship('Campaign', foreign_keys=[call_in_campaign_id])

    def __str__(self):
        # use e164 for external apis, but international formatting for display
        return self.number.international

    @classmethod
    def available_numbers(*args, **kwargs):
        # returns all existing numbers
        return TwilioPhoneNumber.query
        # should filter_by(call_in_allowed=False), and also include numbers for this campaign

    def set_call_in(self, campaign):
        twilio_client = current_app.config.get('TWILIO_CLIENT')
        twilio_app_data = {'friendly_name': 'CallPower (%s)' % campaign.name}

        # set twilio_app VoiceUrl post to campaign url
        campaign_call_url = (url_for('call.incoming', _external=True) +
            '?campaignId=' + str(campaign.id))
        twilio_app_data['voice_url'] = campaign_call_url
        twilio_app_data['voice_method'] = "POST"

        # set twilio_app StatusCallback post for completed event
        campaign_status_url = url_for('call.status_inbound', _external=True, campaignId=str(campaign.id))
        twilio_app_data['status_callback'] = campaign_status_url
        twilio_app_data['status_callback_method'] = "POST"

        # get or create twilio app by campaign name
        existing_apps = twilio_client.applications.list(friendly_name=twilio_app_data['friendly_name'])
        if existing_apps:
            app_sid = existing_apps[0].sid  # there can be only one!
            twilio_app = twilio_client.applications(app_sid).fetch()
            twilio_app.update(**twilio_app_data)
        else:
            twilio_app = twilio_client.applications.create(**twilio_app_data)

        success = (twilio_app.voice_url == campaign_call_url)

        # set twilio call_in_number to use app
        call_in_number = twilio_client.incoming_phone_numbers(self.twilio_sid).fetch()
        call_in_number.update(voice_application_sid=twilio_app.sid)
        self.twilio_app = twilio_app.sid
        self.call_in_campaign_id = campaign.id

        return success


class AudioRecording(db.Model):
    __tablename__ = 'campaign_recording'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(STRING_LEN), nullable=False)

    file_storage = db.Column(FlaskStoreType(location='audio/'), nullable=True)
    text_to_speech = db.Column(db.Text)
    version = db.Column(db.Integer)
    description = db.Column(db.String(STRING_LEN))

    hidden = db.Column(db.Boolean, default=False)

    __table_args__ = (UniqueConstraint('key', 'version'),)

    def file_url(self):
        if self.file_storage:
            return self.file_storage.absolute_url
        else:
            return None

    def campaign_names(self):
        recordings = self.campaign_audio_recordings.all()
        names = set([s.campaign.name for s in recordings])
        return ','.join(list(names))

    def campaign_ids(self):
        recordings = self.campaign_audio_recordings.all()
        ids = set([s.campaign.id for s in recordings])
        return list(ids)

    def selected_recordings(self):
        return self.campaign_audio_recordings.filter_by(selected=True).all()

    def selected_campaign_names(self):
        names = set([s.campaign.name for s in self.selected_recordings()])
        return ','.join(list(names))

    def selected_campaign_ids(self):
        ids = set([s.campaign.id for s in self.selected_recordings()])
        return list(ids)

    def __str__(self):
        return "%s v%s" % (self.key, self.version)


class CampaignAudioRecording(db.Model):
    __tablename__ = 'campaign_audio_recordings'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign_campaign.id'))
    recording_id = db.Column(db.Integer, db.ForeignKey('campaign_recording.id'))
    selected = db.Column(db.Boolean, default=False)

    campaign = db.relationship('Campaign')
    recording = db.relationship('AudioRecording', backref=db.backref('campaign_audio_recordings',
                                                                     lazy='dynamic'))
