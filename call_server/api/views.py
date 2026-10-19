from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
import dateutil

import twilio.twiml
from flask import Blueprint, Response, current_app, render_template, abort, request, jsonify
from werkzeug.datastructures import Headers

from sqlalchemy.sql import func, extract, distinct, cast, join
from flask_talisman import ALLOW_FROM

from .decorators import api_key_or_auth_required, admin_user_required, restless_api_auth
from .constants import API_TIMESPANS

from ..extensions import csrf, cors, rest, db, cache, talisman, CALLPOWER_CSP
from ..campaign.models import Campaign, Target, AudioRecording
from ..political_data.adapters import adapt_by_key, UnitedStatesData
from ..call.models import Call, Session
from ..schedule.models import ScheduleCall
from ..call.constants import TWILIO_CALL_STATUS


api = Blueprint('api', __name__, url_prefix='/api')
csrf.exempt(api)
cors(api)

restless_preprocessors = {'GET_SINGLE':   [restless_api_auth],
                          'GET_MANY':     [restless_api_auth],
                          'PATCH_SINGLE': [restless_api_auth],
                          'PATCH_MANY':   [restless_api_auth],
                          'PUT_SINGLE':   [restless_api_auth],
                          'PUT_MANY':     [restless_api_auth],
                          'POST':         [restless_api_auth],
                          'DELETE':       [restless_api_auth]}


def configure_restless(app):
    rest.create_api(Call, collection_name='call', methods=['GET'],
                    only=['id', 'timestamp', 'campaign_id', 'target_id',
                                    'call_id', 'status', 'duration'],
                    additional_attributes=['target_display'])
    rest.create_api(ScheduleCall, collection_name='schedule', methods=['GET'],
                    only=['id', 'created_at', 'subscribed',
                                    'campaign_id', 'time_to_call', 'last_called', 'num_calls'],
                    additional_attributes=['user_phone'])
    rest.create_api(Campaign, collection_name='campaign', methods=['GET'],
                    only=['id', 'name', 'campaign_type', 'campaign_state', 'campaign_subtype',
                                     'target_ordering', 'allow_call_in', 'call_maximum', 'embed'],
                    additional_attributes=['phone_numbers', 'targets', 'status', 'audio_msgs', 'required_fields'])
    rest.create_api(Target, collection_name='target', methods=['GET'],
                    only=['id', 'uid', 'name', 'title'],
                    additional_attributes=['phone_number'])
    rest.create_api(AudioRecording, collection_name='audiorecording', methods=['GET'],
                    only=['id', 'key', 'version', 'description',
                                     'text_to_speech', 'hidden'],
                    additional_attributes=['file_url', 'campaign_names', 'campaign_ids',
                                     'selected_campaign_names', 'selected_campaign_ids'])


# non CRUD-routes
# protect with decorator

# simple campaign names
@api.route('/campaigns.json', methods=['GET'])
@api_key_or_auth_required
def campaign_list():
    campaigns = Campaign.query.all()
    data = {}
    for campaign in campaigns:
        data[campaign.id] = campaign.name
    return jsonify({'count': len(data), 'objects': data})

# overall campaigns call by date
@api.route('/campaign/date_calls.json', methods=['GET'])
@api_key_or_auth_required
def campaigns_overall():
    start = request.values.get('start')
    end = request.values.get('end')
    timespan = request.values.get('timespan', 'day')

    if timespan not in API_TIMESPANS.keys():
        abort(400, 'timespan should be one of %s' % ','.join(API_TIMESPANS))
    else:
        timespan_strf, timespan_to_char = API_TIMESPANS[timespan]

    timestamp_to_char = func.to_char(Call.timestamp, timespan_to_char).label(timespan)

    query = (
        db.session.query(
            func.min(Call.timestamp.label('date')),
            Call.campaign_id,
            timestamp_to_char,
            func.count(distinct(Call.id)).label('calls_count')
        )
        .group_by(Call.campaign_id)
        .group_by(timestamp_to_char)
        .order_by(timespan)
    )

    completed_query = db.session.query(
        Call.timestamp, Call.id
    ).filter_by(
        status='completed'
    )

    if start:
        try:
            startDate = dateutil.parser.parse(start)
        except ValueError:
            abort(400, 'start should be in isostring format')
        query = query.filter(Call.timestamp >= startDate)
        completed_query = completed_query.filter(Call.timestamp >= startDate)

    if end:
        try:
            endDate = dateutil.parser.parse(end)
            if start:
                if endDate < startDate:
                    abort(400, 'end should be after start')
                if endDate == startDate:
                    endDate = startDate + timedelta(days=1)
        except ValueError:
            abort(400, 'end should be in isostring format')
        query = query.filter(Call.timestamp <= endDate)
        completed_query = completed_query.filter(Call.timestamp <= endDate)

    dates = defaultdict(dict)
    for (date, campaign_id, timespan, count) in query.all():
        date_string = date.strftime(timespan_strf)
        dates[date_string][int(campaign_id)] = count
    sorted_dates = OrderedDict(sorted(dates.items()))

    meta = {
        'calls_completed': completed_query.count()
    }

    return jsonify({'meta': meta,'objects': sorted_dates})


# more detailed campaign statistics
@api.route('/campaign/<int:campaign_id>/stats.json', methods=['GET'])
@api_key_or_auth_required
def campaign_stats(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()

    # number of sessions started in campaign
    # total count and average queue_delay
    sessions_started, queue_avg_timedelta = db.session.query(
        func.count(Session.id).label('count'),
        func.avg(Session.queue_delay).label('queue_avg')
    ).filter_by(
        campaign_id=campaign.id
    ).all()[0]
    if isinstance(queue_avg_timedelta, timedelta):
        queue_avg_seconds = queue_avg_timedelta.total_seconds()
    else:
        queue_avg_seconds = ''

    # number of sessions with at least one completed call in campaign
    sessions_completed = (db.session.query(func.count(Session.id.distinct()))
        .select_from(join(Session, Call))
        .filter(Call.campaign_id==campaign.id,
            Call.status=='completed'
        )
    ).scalar()

    # number of calls completed in campaign
    calls_completed = db.session.query(
        Call.timestamp, Call.id
    ).filter_by(
        campaign_id=campaign.id,
        status='completed'
    )

    # get completed calls per session in campaign
    calls_per_session = db.session.query(
        func.count(Call.id.distinct()).label('call_count'),
    ).filter(
        Call.campaign_id == campaign.id,
        Call.status == 'completed',
        Call.session_id != None
    ).group_by(
        Call.session_id
    )
    calls_per_session_avg = db.session.query(
        func.avg(calls_per_session.subquery().columns.call_count),
    )
    # use this one weird trick to calculate the median
    # https://stackoverflow.com/a/27826044
    calls_per_session_med = db.session.query(
        func.percentile_cont(0.5).within_group(
            calls_per_session.subquery().columns.call_count.desc()
        )
    )
    # calls_session_list = [int(n[0]) for n in calls_session_grouped.all()]
    calls_per_session = {
        'avg': '%.2f' % (calls_per_session_avg.scalar() or 0),
        'med': calls_per_session_med.scalar() or '?'
    }

    data = {
        'id': campaign.id,
        'name': campaign.name,
        'sessions_started': sessions_started,
        'queue_avg_seconds': queue_avg_seconds,
        'sessions_completed': sessions_completed,
        'calls_per_session': calls_per_session,
        'calls_completed': calls_completed.count()
    }

    if data['calls_completed']:
        first_call_completed = calls_completed.first()
        last_call_completed = calls_completed.order_by(Call.timestamp.desc()).first()
        data.update({
            'date_start': datetime.strftime(first_call_completed[0], '%Y-%m-%d'),
            'date_end': datetime.strftime(last_call_completed[0] + timedelta(days=1), '%Y-%m-%d'),
        })

    return jsonify(data)


# calls grouped by timespan
@api.route('/campaign/<int:campaign_id>/date_calls.json', methods=['GET'])
@api_key_or_auth_required
def campaign_date_calls(campaign_id):
    start = request.values.get('start')
    end = request.values.get('end')
    timespan = request.values.get('timespan', 'day')

    if timespan not in API_TIMESPANS.keys():
        abort(400, 'timespan should be one of %s' % ','.join(API_TIMESPANS))
    else:
        timespan_strf, timespan_to_char = API_TIMESPANS[timespan]

    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    timestamp_to_char = func.to_char(Call.timestamp, timespan_to_char).label(timespan)

    query = (
        db.session.query(
            func.min(Call.timestamp.label('date')),
            timestamp_to_char,
            Call.status,
            func.count(distinct(Call.id)).label('calls_count')
        )
        .filter(Call.campaign_id == int(campaign.id))
        .group_by(timestamp_to_char)
        .order_by(timespan)
        .group_by(Call.status)
    )

    if start:
        try:
            startDate = dateutil.parser.parse(start)
        except ValueError:
            abort(400, 'start should be in isostring format')
        query = query.filter(Call.timestamp >= startDate)

    if end:
        try:
            endDate = dateutil.parser.parse(end)
            if start:
                if endDate < startDate:
                    abort(400, 'end should be after start')
                if endDate == startDate:
                    endDate = startDate + timedelta(days=1)
        except ValueError:
            abort(400, 'end should be in isostring format')
        query = query.filter(Call.timestamp <= endDate)

    dates = defaultdict(dict)

    for (date, timespan, call_status, count) in query.all():
        # combine status values by date
        for status in TWILIO_CALL_STATUS:
            if call_status == status:
                date_string = date.strftime(timespan_strf)
                dates[date_string][status] = count
    sorted_dates = OrderedDict(sorted(dates.items()))
    return jsonify({'objects': sorted_dates})


# calls made by target
@api.route('/campaign/<int:campaign_id>/target_calls.json', methods=['GET'])
@api_key_or_auth_required
def campaign_target_calls(campaign_id):
    start = request.values.get('start')
    end = request.values.get('end')

    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()

    query_call_targets = (
        db.session.query(
            Target.title,
            Target.name,
            Target.key
        ).join(Call)
        .filter(Call.campaign_id == int(campaign.id))
        .group_by(Target.title)
        .group_by(Target.name)
        .group_by(Target.key)
    )

    if start:
        try:
            startDate = dateutil.parser.parse(start)
        except ValueError:
            abort(400, 'start should be in isostring format')
        query_call_targets = query_call_targets.filter(Call.timestamp >= startDate)

    if end:
        try:
            endDate = dateutil.parser.parse(end)
            if endDate < startDate:
                abort(400, 'end should be after start')
            if endDate == startDate:
                endDate = startDate + timedelta(days=1)
        except ValueError:
            abort(400, 'end should be in isostring format')
        query_call_targets = query_call_targets.filter(Call.timestamp <= endDate)

    targets = defaultdict(dict)
    political_data = campaign.get_campaign_data().data_provider

    for (target_title, target_name, target_uid) in query_call_targets:
        # get more target_data from political_data cache
        try:
            target_data = political_data.cache_get(target_uid)[0]
        except (KeyError,IndexError):
            target_data = political_data.cache_get(target_uid)
        except Exception as e:
            current_app.logger.error('unable to cache_get for %s: %s' % (target_uid, e))
            target_data = None

        # use adapter to get title, name and district 
        adapted_data = None
        if ':' in target_uid:
            data_adapter = adapt_by_key(target_uid)
            try:
                if target_data:
                    adapted_data = data_adapter.target(target_data)
                else:
                    adapted_data = data_adapter.target({'title': target_title, 'name': target_name, 'uid': target_uid})
            except AttributeError:
                current_app.logger.error('unable to adapt target_data for %s: %s' % (target_uid, target_data))

        elif political_data.country_code.lower() == 'us' and campaign.campaign_type == 'congress':
            # fall back to USData, which uses bioguide
            if not target_data:
                try:
                    target_data = political_data.get_bioguide(target_uid)[0]
                except Exception as e:
                    current_app.logger.error('unable to get_bioguide for %s: %s' % (target_uid, e))
            if target_data:
                try:
                    data_adapter = UnitedStatesData()
                    adapted_data = data_adapter.target(target_data)
                except AttributeError:
                    current_app.logger.error('unable to adapt target_data for %s: %s' % (target_uid, target_data))
            else:
                current_app.logger.error('no target_data for %s' % target_uid)

        if adapted_data:    
            targets[target_uid]['title'] = adapted_data.get('title')
            targets[target_uid]['name'] = adapted_data.get('name')
            targets[target_uid]['district'] = adapted_data.get('district')
        else:
            targets[target_uid]['title'] = target_title
            targets[target_uid]['name'] = target_name
            targets[target_uid]['district'] = target_uid

    # query calls to count status
    query_target_status = query_call_targets.group_by(Call.status).with_entities(Call.status, Target.key, func.Count(Call.id))

    for (call_status, target_uid, count) in query_target_status:
        if call_status in TWILIO_CALL_STATUS:
            # combine calls status for each target
            targets[target_uid][call_status] = targets.get(target_uid, {}).get(call_status, 0) + count

    return jsonify({'objects': targets})


# exports CSV of user phone numbers making successful calls in this campaign
# returns real user data streamed from twilio api, so admin role is required
@api.route('/campaign/<int:campaign_id>/user_phones.csv', methods=['GET'])
@admin_user_required
def user_phones_for_campaign(campaign_id):
    start = request.values.get('start')
    end = request.values.get('end')
    status = request.values.get('status', 'completed')

    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()

    # get sessions for campaign, limited by start/end dates
    query = db.session.query(
        Call.session_id,
        func.Max(Call.call_id),
    ).filter(
        Call.campaign_id == campaign.id,
        Call.status == status,
        Call.session_id != None
    ).group_by(
        Call.session_id
    )

    if start:
        try:
            startDate = dateutil.parser.parse(start)
        except ValueError:
            abort(400, 'start should be in isostring format')
        query = query.filter(Call.timestamp >= startDate)

    if end:
        try:
            endDate = dateutil.parser.parse(end)
            if start:
                if endDate < startDate:
                    abort(400, 'end should be after start')
                if endDate == startDate:
                    endDate = startDate + timedelta(days=1)
        except ValueError:
            abort(400, 'end should be in isostring format')
        query = query.filter(Call.timestamp <= endDate)

    campaign_sessions = query
    twilio_client = current_app.config['TWILIO_CLIENT']

    # use an internal generator so we can stream the response
    def generate():
        # for each session, get the twilio_sid
        # return the user phone (depending on direction)

        for (session_id,call_id) in campaign_sessions:
            session = Session.query.get(session_id)
            try:
                twilio_call = twilio_client.calls.get(call_id).fetch()
                # we want the user's phone number, which is either twilio_call.to or from_
                # depending on direction (can be inbound, outbound-api, outbound-dial, or trunking)
                if twilio_call.direction == 'inbound':
                    user_phone = twilio_call.from_
                elif twilio_call.direction.startswith('outbound'):
                    user_phone = twilio_call.to


                if session.location:
                    yield f"{session.timestamp},{user_phone},{session.location}\n"
                else:
                    yield f"{session.timestamp},{user_phone},\n"
            except twilio.base.exceptions.TwilioRestException:
                # if older than 13 months Twilio may no longer have the record online
                yield f"{session.timestamp},,\n"

    headers = Headers()
    filename = 'callpower-log-campaign-%s' % campaign_id
    headers.set('Content-Disposition', 'attachment', filename=filename+'.csv')
    return Response(generate(), mimetype='text/csv', headers=headers)


# returns twilio call sids made to a particular phone number
# searches phone_hash if available, otherwise the twilio api
@api.route('/twilio/calls/to/<phone>/', methods=['GET'])
@api_key_or_auth_required
def call_sids_for_number(phone):

    if current_app.config['LOG_PHONE_NUMBERS']:
        phone_hash = Session.hash_phone(str(phone))
        sessions = db.session.query(Session.id).filter_by(phone_hash=phone_hash).subquery()
        calls = db.session.query(Call.call_id).filter(Call.session_id.in_(sessions)).distinct()
        calls_id_list = [c.call_id for c in calls.all()]
    
    else:
        # not stored locally, need to hit twilio for calls matching to_
        twilio = current_app.config['TWILIO_CLIENT']
        calls_list = twilio.calls.list(to=phone)
        calls_id_list = [c.sid for c in calls_list]

    return jsonify({'objects': calls_id_list})


# returns information for twilio calls with parent_call_sid
@api.route('/twilio/calls/info/<sid>/', methods=['GET'])
@api_key_or_auth_required
def call_info(sid):
    twilio = current_app.config['TWILIO_CLIENT']
    calls = twilio.calls.list(parent_call_sid=sid)
    calls_sorted = sorted(calls, key=lambda v: v.start_time)
    display_fields = ['to', 'from_', 'status', 'duration', 'start_time', 'end_time', 'direction']
    calls_info = []
    for call in calls_sorted:
        call_info = {}
        for field in display_fields:
            call_info[field] = getattr(call, field)
        calls_info.append(call_info)

    return jsonify({'objects': calls_info})


# embed js campaign routes, should be public
# make accessible crossdomain, and cache for 10 min
@api.route('/campaign/<int:campaign_id>/embed.js', methods=['GET'])
@cache.cached(timeout=600)
def campaign_embed_js(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    dsn_public_key = current_app.config.get('SENTRY_DSN_PUBLIC_KEY', '')
    return Response(render_template('api/embed.js',
        campaign=campaign, DSN_PUBLIC_KEY=dsn_public_key
    ), content_type='application/javascript')


@api.route('/campaign/<int:campaign_id>/CallPowerForm.js', methods=['GET'])
@talisman(content_security_policy=CALLPOWER_CSP.copy().update({'script-src':['\'self\'', '\'unsafe-eval\'']}))
# add unsafe-eval, to execute campaign.embed.custom_js
@cache.cached(timeout=600)
def campaign_form_js(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    return Response(render_template('api/CallPowerForm.js', campaign=campaign), content_type='application/javascript')


@api.route('/campaign/<int:campaign_id>/embed_iframe.html', methods=['GET'])
@cache.cached(timeout=600)
@talisman(frame_options=None) # allow iframe'ing on this route only
def campaign_embed_iframe(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    return render_template('api/embed_iframe.html', campaign=campaign)


@api.route('/campaign/<int:campaign_id>/embed_code.html', methods=['GET'])
@api_key_or_auth_required
def campaign_embed_code(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    # kludge new params into campaign object to render
    temp_params = {
        'type': request.values.get('embed_type'),
        'form_sel': request.values.get('embed_form_sel', None),
        'phone_sel': request.values.get('embed_phone_sel', None),
        'location_sel': request.values.get('embed_location_sel', None),
        'custom_css': request.values.get('embed_custom_css'),
        'custom_js': request.values.get('embed_custom_js'),
        'script_display': request.values.get('embed_script_display'),
    }
    if type(campaign.embed) == dict():
        campaign.embed.update(temp_params)
    else:
        campaign.embed = temp_params
    # don't save
    return render_template('api/embed_code.html', campaign=campaign)


# simple call count per campaign as json
# make accessible crossdomain, and cache for 10 min
@api.route('/campaign/<int:campaign_id>/count.json', methods=['GET'])
@cache.cached(timeout=600)
def campaign_count(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()

    # number of calls completed in campaign
    calls_completed = db.session.query(
        func.Count(Call.id)
    ).filter_by(
        campaign_id=campaign.id,
        status='completed'
    )

    # list of sessions with at least two completed calls
    # grouped by referral_code, include count
    referrers = db.session.query(
        Session.referral_code,
        func.Count(Call.id)
    ).join(Call).filter(
        Call.campaign_id==campaign.id,
        Call.status=='completed'
    ).group_by(Session.referral_code)\
    .having(func.count(Call.id) > 2)

    return jsonify({
        'completed': calls_completed.scalar(),
        'last_24h': calls_completed.filter(Call.timestamp >= datetime.now() - timedelta(hours=24)).scalar(),
        'last_week': calls_completed.filter(Call.timestamp >= datetime.now() - timedelta(days=7)).scalar(),
        'referral_codes': dict(referrers)
    })

# route for twilio to get twiml response
# must be publicly accessible to post
@api.route('/twilio/text-to-speech', methods=['POST'])
def twilio_say():
    voice = request.values.get('voice', 'alice')
    lang = request.values.get('lang', 'en')

    resp = twilio.twiml.voice_response.VoiceResponse()
    resp.say(request.values.get('text'), voice=voice, language=lang)
    resp.hangup()
    return str(resp)
