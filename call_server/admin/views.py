from datetime import datetime, timedelta

from flask import Blueprint, render_template, current_app, flash, url_for, redirect, request, session
from flask_login import login_required, current_user
from flask_babel import gettext as _

from ..extensions import db, cache
from sqlalchemy.sql import func, desc

from .models import Blocklist
from .forms import BlocklistForm

from ..campaign.models import TwilioPhoneNumber, Campaign
from ..call.models import Call
from ..sync.models import SyncCampaign
from ..campaign.constants import STATUS_PAUSED
from ..api.constants import API_TIMESPANS
from ..utils import get_one_or_create
from ..user.models import User

admin = Blueprint('admin', __name__, url_prefix='/admin')

# all admin routes require login
@admin.before_request
@login_required
def before_request():
    # check and delete old old python2 cookies before rendering 
    if type(session.get('csrf_token')) is bytes:
        del session['csrf_token']


@admin.route('/')
def dashboard():
    campaigns = (Campaign.query
        .filter(Campaign.status_code >= STATUS_PAUSED)
        .order_by(desc(Campaign.status_code), desc(Campaign.id))
    )
    calls_by_campaign = (db.session.query(Campaign.id, func.count(Call.id))
            .filter(Campaign.status_code >= STATUS_PAUSED)
            .filter(Call.status == 'completed')
            .join(Call).group_by(Campaign.id))

    today = datetime.today().replace(hour=0, minute=0, second=0)
    this_month_start = today.replace(day=1)  # first day of the current month
    last_month = this_month_start - timedelta(days=28) # a day in last month
    next_month = today.replace(day=28) + timedelta(days=4)  # a day in next month (for months with 28,29,30,31)

    this_month_end = next_month - timedelta(days=next_month.day)  # the last day of the current month
    this_month_end = this_month_end.replace(hour=23, minute=59)
    last_month_start = last_month - timedelta(days=(last_month.day-1))
    last_month_end = this_month_start - timedelta(days=this_month_start.day)
    last_month_end = last_month_end.replace(hour=23, minute=59)

    calls_this_month = (db.session.query(func.count(Call.id))
            .filter(Call.status == 'completed')
            .filter(Call.timestamp >= this_month_start)
            .filter(Call.timestamp <= this_month_end)
        ).scalar()

    calls_last_month = (db.session.query(func.count(Call.id))
            .filter(Call.status == 'completed')
            .filter(Call.timestamp >= last_month_start)
            .filter(Call.timestamp <= last_month_end)
        ).scalar()

    calls_by_day = (db.session.query(func.date(Call.timestamp), func.count(Call.id))
            .filter(Call.status == 'completed')
            .filter(Call.timestamp >= this_month_start)
            .filter(Call.timestamp <= this_month_end)
            .group_by(func.date(Call.timestamp))
            .order_by(func.date(Call.timestamp))
        )

    return render_template('admin/dashboard.html',
        campaigns=campaigns,
        calls_by_campaign=dict(calls_by_campaign.all()),
        calls_by_day=calls_by_day.all(),
        calls_this_month=calls_this_month,
        calls_last_month=calls_last_month,
    )


@admin.route('/statistics')
def statistics():
    campaigns = Campaign.query.order_by(desc(Campaign.status_code), desc(Campaign.id)).all()
    today = datetime.today().replace(hour=0, minute=0, second=0)
    this_month_start = today.replace(day=1)  # first day of the current month

    last_month = this_month_start - timedelta(days=28) # a day in last month
    next_month = today.replace(day=28) + timedelta(days=4)  # a day in next month (for months with 28,29,30,31)

    last_month_start = last_month - timedelta(days=(last_month.day-1))
    this_month_end = next_month - timedelta(days=next_month.day)  # the last day of the current month
    return render_template('admin/statistics.html',
        campaigns=campaigns, timespans=API_TIMESPANS,
        default_start=last_month_start.strftime('%Y/%m/%d'),
        default_end=this_month_end.strftime('%Y/%m/%d'))


@admin.route('/system')
def system():
    twilio_numbers = TwilioPhoneNumber.query.all()
    admin_api_key = current_app.config.get('ADMIN_API_KEY')
    twilio_account = current_app.config.get('TWILIO_CLIENT').auth[0]
    crm_sync_campaigns = SyncCampaign.query.all()

    political_data_cache = {'US': cache.get('political_data:us'),
                            'CA': cache.get('political_data:ca')}
    blocked = Blocklist.query.order_by(Blocklist.timestamp.desc()).all()
    if not political_data_cache['US']:
        flash(_("US Political Data not yet loaded. Run > flask loadpoliticaldata") , 'warning')
    return render_template('admin/system.html',
                           message_defaults=current_app.config.CAMPAIGN_MESSAGE_DEFAULTS,
                           twilio_numbers=twilio_numbers,
                           twilio_account=twilio_account,
                           admin_api_key=admin_api_key,
                           crm_sync_campaigns=crm_sync_campaigns,
                           political_data_cache=political_data_cache,
                           blocked=blocked)


@admin.route('/system/blocklist/create', methods=['GET', 'POST'])
@admin.route('/system/blocklist/<int:blocklist_id>/edit', methods=['GET', 'POST'])
def blocklist(blocklist_id=None):
    edit = False
    if blocklist_id:
        edit = True

    if edit:
        blocklist = Blocklist.query.filter_by(id=blocklist_id).first_or_404()
    else:
        blocklist = Blocklist()

    form = BlocklistForm()
    
    if form.is_submitted() and form.validate():
        form.populate_obj(blocklist)

        db.session.add(blocklist)
        db.session.commit()

        flash('Blocklist updated.', 'success')
        return redirect(url_for('admin.system'))

    return render_template('admin/blocklist.html', blocklist=blocklist, form=form)


# for flask-limit exempt-when
# called with request context
def admin_phone():
    if current_user.is_authenticated:
        return True

    # if calling from embedded website, check list of admin users
    phone = request.values.get('userPhone')
    return phone in current_app.ADMIN_PHONES_LIST

@admin.route('/twilio/resync', methods=['POST'])
def twilio_resync():
    """ One-way sync of Twilio numbers from REST Client down to our database
    Adds new numbers, saves voice_application_sid, and removes stale entries."""

    client = current_app.config.get('TWILIO_CLIENT')
    twilio_numbers = client.incoming_phone_numbers.list()

    new_numbers = []
    deleted_numbers = []
    for num in twilio_numbers:
        obj, created = get_one_or_create(db.session, TwilioPhoneNumber,
                                         number=num.phone_number,
                                         twilio_sid=num.sid)
        if created:
            new_numbers.append(num.phone_number)

        # update voice application sid from twilio
        obj.twilio_app = num.voice_application_sid
        db.session.add(obj)
        db.session.commit()

    # find any stale numbers we have in the db that aren't in the response
    stale_numbers = TwilioPhoneNumber.query.filter(
        TwilioPhoneNumber.number.notin_([n.phone_number for n in twilio_numbers]))
    # and remove them
    # TODO, check if delete will cascade to campaign
    for num in stale_numbers.all():
        deleted_numbers.append(str(num.number))
        db.session.delete(num)
    db.session.commit()

    if new_numbers:
        flash(_("Added Twilio Number: ") + ', '.join(new_numbers), 'success')
    if deleted_numbers:
        flash(_("Removed Twilio Number: ") + ', '.join(deleted_numbers), 'warning')
    else:
        flash(_("Twilio Numbers are Up to Date"), 'success')

    return redirect(url_for('admin.system'))
