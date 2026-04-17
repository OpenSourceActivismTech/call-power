Installation
==============

Configure Settings
------------

The app requires several account keys to run. These should not be stored in version control, but in environment variables. For development, you can export these from your virtualenv/bin/activate script, or put them in a .env file and load them with [autoenv](https://github.com/kennethreitz/autoenv).

At a minimum, you will need to set:

* SECRET_KEY, to secure login sessions cryptographically
    * This will be created for you automatically if you use the deploy to Heroku button, or you can generate one using with this Javascript one-liner: `chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890-=!@#$%^&*()_+:<>{}[]".split(''); key = ''; for (i = 0; i < 50; i++) key += chars[Math.floor(Math.random() * chars.length)]; alert(key);`
* TWILIO_ACCOUNT_SID, for an account with at least one purchased phone number
* TWILIO_AUTH_TOKEN, for the same account
* INSTALLED_ORG, displayed on the site homepage and read in intro messages
* SITENAME, defaults to CallPower

To lookup individual representatives, you need:

* US Congress contact information is provided in call_server/political_data/data. [Update instructions](/OPEN_DATA_SOURCES.md#update-instructions)
* OPENSTATES_API_KEY, to perform state legislative lookups. Sign up for one at [OpenStates.org](https://openstates.org/api/register/)
* GEOCODE_PROVIDER must be one of ('Google', 'Nominatim', or 'SmartyStreets'). We suggest Google for international campaigns.
* GEOCODE_API_KEY as required by the provider. Google and SmartyStreets require keys, Nominatim does not.

To test Twilio functionality in development, you will need your server to have a web-routable address. 

* Twilio provides [ngrok](https://ngrok.com) to do this for free. When using the debug server you can use `USE_NGROK=TRUE; python manage.py runserver`
* To test text-to-speech playback in the browser, you will need to create a [TwiML app](https://www.twilio.com/user/account/apps) with the Voice request URL http://YOUR_HOSTNAME/api/twilio/text-to-speech. Place the resulting application SID in your environment as TWILIO_PLAYBACK_APP

For production, you will also need to set:

* CALLPOWER_CONFIG='call_server.config:ProductionConfig', so that manager.py knows to use a real database for migrations
* DATABASE_URI, a sqlalchemy [connection string](https://pythonhosted.org/Flask-SQLAlchemy/config.html#connection-uri-format) for a postgres or mysql database addresses
* REDIS_URL, a URI for the Redis server
* APPLICATION_ROOT to the path where the application will live. If you are using a whole domain or subdomain, this should be set to '/'.
* SERVER_NAME to the domain or subdomain on which the application will live (if this is not set, external urls will default to localhost)
* CALL_RATE_LIMIT, the maximum number of allowed calls to a phone number for each campaign, to limit abuse potential. Admin phone numbers and logged in users are exempt. Defaults to "2 / hour", and must be specified in [flask-limit notation](https://flask-limiter.readthedocs.io/en/stable/#rate-limit-string-notation).
* WEB_THREADS to set the number of Gunicorn threads (default to 4)

If you are storing assets on Amazon S3, or another [Flask-Store provider](http://flask-store.soon.build)

* STORE_S3_BUCKET
* STORE_S3_REGION (eg: us-east-1, or us-west-2)
* STORE_DOMAIN (automatically set by S3 region and bucket, override if you are using another provider)
* S3_ACCESS_KEY
* S3_SECRET_KEY

If you would like to let users reset their passwords over email:

* MAIL_SERVER, defaults to `localhost`
* MAIL_PORT, defaults to 25
* MAIL_USERNAME
* MAIL_PASSWORD
* MAIL_DEFAULT_SENDER, defaults to `info@callpower.org`

For more information on default configuration values, check the [Flask Documentation](http://flask.pocoo.org/docs/0.10/config/#builtin-configuration-values)

Development mode
-------------------
To install locally and run in debug mode use:

    # create ENV variables
    virtualenv .venv
    source .venv/bin/activate
    pip install -r requirements/development.txt
    export FLASK_APP=manager.py; FLASK_ENV=development; FLASK_DEBUG=1

    # create the database
    python3 manage.py migrate

    # compile assets
    npm install -g bower
    bower install
    flask assets build
    
    # create an admin user
    python3 manage.py createadminuser

    # if testing twilio, run in another tab
    ngrok http 5000
 
    # run local server for debugging, pass subdomain from ngrok and bind to external host
    export SERVER_NAME={{subdomain}}.ngrok.io
    flask run --host=0.0.0.0

    # if testing scheduled calls, run the Django scheduler loop in a new tab
    python3 manage.py runjobs

When the dev server is running, the front-end will be accessible at [http://localhost:5000/](http://localhost:5000/), and proxied to external routes at [http://ngrok.com](http://ngrok.com).

Unit tests can also be run with:

    python tests/run.py

Production server
------------------
To run in production, with compiled assets:

    # create ENV variables
    export FLASK_APP=manager.py
    
    # open correct port
    iptables -A INPUT -p tcp --dport 80 -j ACCEPT
    
    # initialize the database
    python3 manage.py migrate
    
    # create an admin user (with optional --username, --password, --email)
    python3 manage.py createadminuser

    # prime cache with political data
    python3 manage.py loadpoliticaldata

    # if you are running a reverse proxy, you can start the application with foreman start
    foreman start

    # or point your WSGI server to `call_server.wsgi:application`
    # to load the application directly

    # if you wish to enable recurring outbound calls, run the Django scheduler loop
    python3 manage.py runjobs
    
Make sure your webserver can serve audio files out of `APPLICATION_ROOT/instance/uploads`. Or if you are using Amazon S3, ensure your buckets are configured for public access.

Heroku setup
------------------
Heroku names some environment variables differently, particularly for the database and redis cache. To ensure the correct ones are pulled in, ensure that the Heroku config is enabled by setting `heroku config:set CALLPOWER_CONFIG=call_server.config:HerokuConfig`.

You will also need to provision the Heroku Postgres and Heroku Redis addons for database and caching,. You can start with the Hobby tiers which are free to test, but for production use you'll want to upgrade to Standard. You will probably also want to add Sendgrid to send user invite and password resset emails; this can likely remain at the Starter level.

Docker setup
------------------
A Dockerfile is included for building a container environment suitable for both development and production. To begin, copy `docker-compose.yml.example` to `docker-compose.yml` and fill in the appropriate values. Consult [the first part of this guide](#configure-settings) to learn what the required variables are.

In the dockerized environment, there is one additional variable which may be set. `FLASK_ENV` will be consulted in the container's entrypoint to determine how to boot the app:

FLASK_ENV           | Result
--------------------|--------
production          | App is brought up using `uwsgi`. In this case, the environment variable `PORT` should also be set.
development         | App is brought up with flask's built in http server.
development-expose  | App is brought up with flask's built in http server and then exposed externally using `ngrok`. Use this environment to test twilio functionality.

If `FLASK_ENV` is not provided, the default is to bring the app up in the development environment.

Testing
------------------
To run the full test suite, `python tests/run.py`
Or just a subset `python tests/run.py test_us_data.TestUSData`


Performance Tips
--------------------------------

We use the Gunicorn WSGI server with async workers in production.

[Their docs](http://docs.gunicorn.org/en/latest/design.html#how-many-workers) recommend (2 x $num_cores) + 1 as a number of workers. For a regular (1x) Heroku dyno with 512mb RAM, this means WEB_CONCURRENCY=3 and WEB_THREADS=4
