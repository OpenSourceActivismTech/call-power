# TODO, figure out how to load gevent monkey patch cleanly in production
# try:
#     from gevent.monkey import patch_all
#     patch_all()
#     import psycogreen.gevent
#     psycogreen.gevent.patch_psycopg()
# except ImportError:
#     print("unable to apply gevent monkey.patch_all")

import os

from werkzeug.middleware.proxy_fix import ProxyFix

from call_server.app import create_app
from call_server.extensions import assets

assets._named_bundles = {}
application = create_app()
# requires application context
assets.auto_build = False

application.wsgi_app = ProxyFix(application.wsgi_app)
