import os
import sys
from datetime import datetime

import click
import alembic
import alembic.config, alembic.command

from call_server.app import create_app
from call_server.extensions import assets, db, cache, rq
from call_server import political_data
from call_server import sync
from call_server.user import User, USER_ADMIN, USER_ACTIVE

app = create_app()
app.db = db

alembic_config = alembic.config.Config(os.path.realpath(os.path.dirname(__name__)) + "/alembic.ini")
# let the config override the default db location in production
alembic_config.set_section_option('alembic', 'sqlalchemy.url',
                                  app.config.get('SQLALCHEMY_DATABASE_URI'))


def reset_assets():
    """Reset assets named bundles to {} before running command.
    This command should really be run with TestingConfig context"""
    app.logger.info("resetting assets")
    assets._named_bundles = {}


@app.cli.command()
@click.option('--external', default=None, help='externally routable domain')
def runserver(external=None):
    app.logger.error('deprecated, use flask run instead')
    sys.exit(-1)

@app.cli.command()
def loadpoliticaldata():
    """Load political data into persistent cache"""
    # try:
    #     import gevent.monkey
    #     gevent.monkey.patch_thread()
    # except ImportError:
    #     app.logger.warning("unable to apply gevent monkey.patch_thread")
    from flask_babel import force_locale

    app.logger.info("loading political data")
    with app.app_context(), force_locale('en'):
            n = political_data.load_data(cache)
    app.logger.info("done loading %d objects" % n)

@app.cli.command()
@click.argument('campaign_id')
@click.argument('date', default=datetime.today().date().isoformat())
def stop_scheduled_calls(campaign_id, date):
    # unsubscribe outgoing recurring calls created before date
    from call_server.campaign import Campaign
    from call_server.schedule import ScheduleCall
    before_date = datetime.strptime(date, '%Y-%m-%d')
    campaign = Campaign.query.get(campaign_id)
    scheduled_calls = ScheduleCall.query.filter(campaign==campaign, ScheduleCall.created_at <= before_date).all()
    print('This will stop all {} scheduled calls for campaign {} created before {}'.format(len(scheduled_calls), campaign.name, date))
    confirm = input('Confirm (Y/N): ')
    if confirm == 'Y':
        for sc in scheduled_calls:
            print("canceling job", sc.job_id)
            sc.stop_job()
            db.session.add(sc)
        db.session.commit()
        print("done")
    else:
        print("exit")

@app.cli.command()
@click.argument('campaign_id', default='all')
@click.option('--accept_all', default=False, help='skip ')
def restart_scheduled_calls(campaign_id, accept_all=False):
    # rebind outgoing recurring calls
    from call_server.campaign import Campaign
    from call_server.campaign.constants import STATUS_LIVE
    from call_server.schedule import ScheduleCall

    if campaign_id == 'all':
        campaigns = Campaign.query.filter_by(prompt_schedule=True, status_code=STATUS_LIVE).all()
    else:
        campaigns = [Campaign.query.get(campaign_id),]

    print('This will restart all subscribed scheduled calls for campaign {}'.format(campaign_id))
    if accept_all:
        confirm = 'Y'
    else:
        confirm = input('Confirm (Y/N): ')
    if confirm == 'Y':
        for campaign in campaigns:
            scheduled_calls = ScheduleCall.query.filter_by(campaign=campaign, subscribed=True).all()
            print('Scheduled calls for {}: {}'.format(campaign.name, len(scheduled_calls)))
            rq_scheduler = rq.get_scheduler()
            for sc in scheduled_calls:
                if not sc.job_id in rq_scheduler:
                    print("resetting job", sc.job_id)
                    sc.start_job()
                    db.session.add(sc)
            db.session.commit()
            print("done")
        else:
            print("exit")

@app.cli.command()
@click.argument('campaigns', default='all')
def crmsync(campaigns):
    print("Sync to CRM")
    if campaigns == 'all':
        campaigns_list = 'all'
    elif ',' in campaigns:
        campaigns_list = campaigns.split(',')
    else:
        campaigns_list = (campaigns,)
    sync.jobs.sync_campaigns(campaigns_list)

@app.cli.command()
@click.argument('campaign_id')
def fixtargets(campaign_id):
    from call_server.campaign import Campaign, Target, CampaignTarget
    from call_server.utils import parse_target

    print("Fixing duplicate campaign targets")
    campaign = Campaign.query.filter_by(id=campaign_id).one()
    # create exclusive set of targets
    target_set = set((t.key) for t in campaign.target_set)
    print("Got %s targets, %s unique" % (len(campaign.target_set), len(target_set)))

    # delete exisiting CampaignTargets
    CampaignTarget.query.filter_by(campaign=campaign).delete()

    # recreate from set
    target_list = []
    for index,target_key in enumerate(list(target_set)):
        # split prefix:uid
        (uid, prefix) = parse_target(target_key)
        print(index,uid)
        # get or create Target
        (target, created) = Target.get_or_create(uid, prefix, commit=False)
        target_list.append(target)
        db.session.add(target)
        
    setattr(campaign, 'target_set', target_list)
    db.session.add(campaign)
    db.session.commit()

@app.cli.command()
def redis_clear():
    print("This will entirely clear the Redis cache")
    confirm = input('Confirm (Y/N): ')
    if confirm == 'Y':
        with app.app_context():
            cache.cache._client.flushdb()
        print("redis cache cleared")
    else:
        print("exit")


@app.cli.command()
@click.argument('direction')
def migrate(direction):
    """Migrate db revision up or down"""
    reset_assets()
    print("migrating %s database at %s" % (direction, app.db.engine.url))
    if direction == "up":
        alembic.command.upgrade(alembic_config, "head")
    elif direction == "down":
        alembic.command.downgrade(alembic_config, "-1")
    else:
        app.logger.error('invalid direction. (up/down)')
        sys.exit(-1)

@app.cli.command()
@click.argument('message')
def migration(message):
    """Create migration file"""
    reset_assets()
    alembic.command.revision(alembic_config, autogenerate=True, message=message)

@app.cli.command()
@click.argument('revision')
def stamp(revision):
    """Fake a migration to a particular revision"""
    reset_assets()
    alembic.command.stamp(alembic_config, revision)


@app.cli.command()
@click.option('--username', default=None)
@click.option('--password', default=None)
@click.option('--email', default=None)
def createadminuser(username, password, email):
    """Create a new admin user, get password from user input or directly via command line"""

    # first, check to see if exact user already exists
    if username and email and password:
        if User.query.filter_by(name=username).count() == 1:
            print("username %s already exists" % username)
            return True

    # else, getpass from raw input
    from getpass import getpass
    from call_server.user.constants import (USERNAME_LEN_MIN, USERNAME_LEN_MAX,
                                            PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)

    while username is None:
        username = input('Username: ')
        if len(username) < USERNAME_LEN_MIN:
            print("username too short, must be at least", USERNAME_LEN_MIN, "characters")
            username = None
            continue
        if len(username) > USERNAME_LEN_MAX:
            print("username too long, must be less than", USERNAME_LEN_MIN, "characters")
            username = None
            continue
        if User.query.filter_by(name=username).count() > 0:
            print("username already exists")
            username = None
            continue

    while email is None:
        email = input('Email: ')
        # email validation necessary?

    while password is None:
        password = getpass('Password: ')
        password_confirm = getpass('Confirm: ')
        if password != password_confirm:
            print("passwords don't match")
            password = None
            continue
        if len(password) < PASSWORD_LEN_MIN:
            print("password too short, must be at least", PASSWORD_LEN_MIN, "characters")
            password = None
            continue
        if len(password) > PASSWORD_LEN_MAX:
            print("password too long, must be less than", PASSWORD_LEN_MAX, "characters")
            password = None
            continue

    admin = User(name=username,
                 email=email,
                 password=password,
                 role_code=USER_ADMIN,
                 status_code=USER_ACTIVE)
    db.session.add(admin)
    db.session.commit()

    print("created admin user", admin.name)

if __name__ == "__main__":
    app.logger.error("please use `flask run` to start")
    sys.exit(-1)
