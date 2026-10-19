import os
import twilio.rest
from ssl import CERT_NONE

class DefaultConfig(object):
    PROJECT = 'CallPower'
    DEBUG = False
    TESTING = False
    VERSION = "1.5.12"
    ENVIRONMENT = os.environ.get('APP_ENVIRONMENT', "Default")

    APP_NAME = "call_server"
    APPLICATION_ROOT = '/'  # the path where the application is configured

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI',
        'sqlite:////%s/dev.db' % os.path.abspath(os.curdir))
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    ACCEPT_LANGUAGES = {'en': 'English',
                        'es': 'Spanish'}

    CACHE_TYPE = 'simple'
    CACHE_THRESHOLD = 100000  # because we're caching political data
    CACHE_DEFAULT_TIMEOUT = 60*60*24*365*2  # there's no infinite timeout, so default to 2 year election cycle

    CSRF_ENABLED = False

    INSTALLED_ORG = os.environ.get('INSTALLED_ORG')
    SITENAME = os.environ.get('SITENAME', PROJECT)

    STORE_PROVIDER = 'flask_store.providers.local.LocalProvider'
    STORE_DOMAIN = 'http://localhost:5000' # requires url scheme for Flask-store.absolute_url to work

    TWILIO_CLIENT = twilio.rest.Client(
        os.environ.get('TWILIO_ACCOUNT_SID'),
        os.environ.get('TWILIO_AUTH_TOKEN'))
    TWILIO_PLAYBACK_APP = os.environ.get('TWILIO_PLAYBACK_APP')
    # limit on the length of the call
    TWILIO_TIME_LIMIT = os.environ.get('TWILIO_TIME_LIMIT', 60 * 60)  # one hour max
    # limit on the amount of time to ring before giving up
    TWILIO_TIMEOUT = os.environ.get('TWILIO_TIMEOUT', 60)  # seconds

    # maximum number of outbound calls to the same phone number, from the same campaign
    # admin phones numbers are exempt, for testing
    CALL_RATE_LIMIT = os.environ.get('CALL_RATE_LIMIT', '2/hour')
    # limit string must match notation like "[count] [per|/] [n (optional)] [second|minute|hour|day|month|year]""
    # from https://flask-limiter.readthedocs.io/en/stable/#rate-limit-string-notation

    SECRET_KEY = os.environ.get('SECRET_KEY')

    GEOCODE_API_KEY = os.environ.get('GEOCODE_API_KEY')
    OPENSTATES_API_KEY = os.environ.get('OPENSTATES_API_KEY')
    if not OPENSTATES_API_KEY:
        OPENSTATES_API_KEY = os.environ.get('OPENSTATES_API_KEY')

    LOG_PHONE_NUMBERS = True

    MAIL_SERVER = 'localhost'

    CRM_INTEGRATION = os.environ.get('CRM_INTEGRATION','').lower()
    if CRM_INTEGRATION == 'actionkit':
        ACTIONKIT_DOMAIN = os.environ.get('ACTIONKIT_DOMAIN')
        ACTIONKIT_USER = os.environ.get('ACTIONKIT_USER')
        ACTIONKIT_API_KEY = os.environ.get('ACTIONKIT_API_KEY')
        ACTIONKIT_PASSWORD = os.environ.get('ACTIONKIT_PASSWORD')
    if CRM_INTEGRATION == 'rogue':
        ROGUE_DOMAIN = os.environ.get('ROGUE_DOMAIN')
        ROGUE_API_KEY = os.environ.get('ROGUE_API_KEY')
    if CRM_INTEGRATION == 'mobilecommons':
        MOBILE_COMMONS_USERNAME = os.environ.get('MOBILE_COMMONS_USERNAME')
        MOBILE_COMMONS_PASSWORD = os.environ.get('MOBILE_COMMONS_PASSWORD')
        MOBILE_COMMONS_COMPANY = os.environ.get('MOBILE_COMMONS_COMPANY')

    if 'STORE_S3_BUCKET' in os.environ:
        STORE_PROVIDER = 'flask_store.providers.s3.S3Provider'
        # TODO, change to S3GeventProvider when we re-enable gevent
        STORE_PATH = 'uploads'
        STORE_S3_BUCKET = os.environ.get('STORE_S3_BUCKET')
        STORE_S3_REGION = os.environ.get('STORE_S3_REGION')
        STORE_S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY')
        STORE_S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY')
    else:
        STORE_PROVIDER = 'flask_store.providers.local.LocalProvider'
        STORE_S3_REGION = ''

    STORE_DOMAIN = os.environ.get('STORE_DOMAIN')
    if not STORE_DOMAIN and STORE_S3_REGION:
        # set external store domain per AWS regions
        # http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region
        # use path-style urls, in case bucket name is DNS incompatible (uses periods, or mixed case
        # http://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html
        if STORE_S3_REGION == 'us-east-1':
            STORE_DOMAIN = 'https://s3.amazonaws.com/%s/' % (STORE_S3_BUCKET)
        else:
            STORE_DOMAIN = 'https://s3-%s.amazonaws.com/%s/' % (STORE_S3_REGION, STORE_S3_BUCKET)

class ProductionConfig(DefaultConfig):
    DEBUG = False

    ENVIRONMENT = "Production"

    SERVER_NAME = os.environ.get('SERVER_NAME')
    APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '/')
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', None)
    PREFERRED_URL_SCHEME = 'https'

    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    CACHE_KEY_PREFIX = 'call-power:'
    RQ_REDIS_URL = os.environ.get('REDIS_URL')
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL')

    LOG_PHONE_NUMBERS = os.environ.get('LOG_PHONE_NUMBERS', False)
    OUTPUT_LOG = os.environ.get('OUTPUT_LOG', False)

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = os.environ.get('MAIL_PORT', 25)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', True)

    SESSION_COOKIE_SECURE = True
    SENTRY_DSN = os.environ.get('SENTRY_DSN', None)

    SQLALCHEMY_POOL_SIZE = int(os.environ.get('SQLALCHEMY_POOL_SIZE', 5))
    SQLALCHEMY_POOL_RECYCLE = os.environ.get('SQLALCHEMY_POOL_RECYCLE', 60 * 60)  # default 1 hour
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')

class HerokuConfig(ProductionConfig):
    # Heroku addons use a few different environment variable names

    ENVIRONMENT = "Production"

    # db via heroku postgres
    # Rewrite the prefix if it uses the deprecated scheme
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_POOL_RECYCLE = 500

    # cache via heroku-redis
    CACHE_TYPE = 'RedisCache'
    redis_url = os.environ.get('REDIS_URL')
    # Rewrite the prefix if it uses the insecure scheme
    if redis_url and redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "rediss://", 1)
    CACHE_REDIS_URL = redis_url
    CACHE_KEY_PREFIX = 'call-power:'
    CACHE_OPTIONS = {'ssl':True, 'ssl_cert_reqs': CERT_NONE}
    # heroku uses self-signed certificates for redis, so don't try to validate them

    # smtp via sendgrid
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USERNAME = os.environ.get('SENDGRID_USERNAME')
    MAIL_PASSWORD = os.environ.get('SENDGRID_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'info@callpower.org')
    MAIL_USE_TLS = True

    # use rq HerokuWorker
    RQ_WORKER_CLASS = 'call_server.sync.worker.CleanSlateHerokuWorker'
    RQ_LOG_LEVEL = os.environ.get('RQ_LOG_LEVEL', 'info')


class DevelopmentConfig(DefaultConfig):
    DEBUG = os.environ.get('FLASK_DEBUG', True)
    DEBUG_MORE = True
    TESTING = False

    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = 'redis://localhost:6379'
    CACHE_KEY_PREFIX = 'call-power:'

    ENVIRONMENT = os.environ.get('APP_ENVIRONMENT', "Development")

    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'ThisIsATestAdminAPIKey!')

    WTF_CSRF_ENABLED = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'NotARealSecretKey,YouShouldSetOneInYour.Env')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI',
        'sqlite:////%s/dev.db' % os.path.abspath(os.curdir))
    # four slashes for an absolute path
    # per http://docs.sqlalchemy.org/en/latest/core/engines.html#sqlite

    SERVER_NAME = os.environ.get('SERVER_NAME', 'localhost:5000')

    if not 'STORE_S3_BUCKET' in os.environ:
        STORE_PATH = '%s/instance/uploads/' % os.path.abspath(os.curdir)
        STORE_DOMAIN = os.environ.get('STORE_DOMAIN', 'http://localhost:5000')

    MAIL_DEBUG = True
    MAIL_PORT = 1025
    MAIL_DEFAULT_SENDER = 'debug'

    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(DefaultConfig):
    ENVIRONMENT = "Testing"

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite://'  # keep testing db in memory
    CACHE_TYPE = 'simple'
    CACHE_NO_NULL_WARNING = True
