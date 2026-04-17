Call Power
==============

Connecting people to power through their phones.

Migration status
----------------

This repository now contains a side-by-side Django + React migration in addition
to the legacy Flask + Backbone application.

- Legacy app: `call_server/`
- New Django app: `django_app/`
- New React admin UI: `frontend/`

The new stack currently ports the admin shell foundation, dashboard summary API,
campaign editing APIs, a Django political-data layer, and an initial Twilio
call-flow foundation while reusing the existing database tables.

The admin interface lets activists:

* Create and edit campaigns
* Adjust call targets and phone numbers
* Record audio prompts and select versions
* Easily embed campaign forms on their website
* View campaign statistics and system analytics

The server lets callers:

* Dial in directly to the campaign number
* Fill out a web form and get a call back on their phone
    * specifying a target directly
    * or entering their zip code to look up their location
* Reference a script during the call


Campaign Configuration
----------------------

1) Create a campaign with one of several types, to determine how callers are matched to targets.

* _Executive_ connects callers to the Whitehouse Switchboard, or to a specific office if known
* _Congress_ connects callers to their Senators, Representative, or both. Uses data from the TheUnitedStates.io.
* _State_ connects callers to their Governor or State Legislators. Uses the OpenStates API.
* _Local_ connects callers to a local official. Campaigners must enter these numbers in advance.
* _Custom_ can connect callers to corporate offices, local officals, or any other phone number entered in advance.

2) Choose targets by segmenting on user location (determined by zipcode or lat/lon), and order by legislative chamber or random shuffle. For local and custom campaigns, campaigners can set a specific order by drag-and-drop.

3) Record audio prompts in the browser (Firefox/Chrome only), or edit with another program and upload as MP3 files. For dynamic prompts, you can also text-to-speech templates. Reuse versions between campaigns, or adjust your prompts as the campaign evolves.

4) Review the campaign setup, place a test call to yourself, and get the script to embed in your action platform. 


Action Integration
------------------
For most uses, you can just place the `<script>` tag provided in the launch page into your action platform. This will add a post-submit callback to your action form to connect the caller, and optionally display the script in a lightbox.

For more complex integrations, Call Power provides [javascript embeds](INTEGRATION_JS.md) and a full [json API](INTEGRATION_API.md).

Individual actions can also be synced to CRMs, via a [batch process](INTEGRATION_CRM.md).

Installation Instructions
-------------------
This application should be easy to host on Heroku, with Docker, or directly on any WSGI-compatible server. Requires Python, flask, a SQL database (we recommend Postgres, but Mysql should work), Redis or Memcache, and an SMTP server.

Read detailed instrustions at [INSTALLATION.md](INSTALLATION.md)

For the Django + React migration, see [django_app/README.md](django_app/README.md).

Testing
-------
`python tests/run.py` 

[![Build Status](https://travis-ci.com/OpenSourceActivismTech/call-power.svg?branch=master)](https://travis-ci.com/OpenSourceActivismTech/call-power)
[![Coverage Status](https://coveralls.io/repos/github/OpenSourceActivismTech/call-power/badge.svg?branch=master)](https://coveralls.io/github/OpenSourceActivismTech/call-power?branch=master)

Political Data
--------------

Political data is downloaded from [open data sources](OPEN_DATA_SOURCES.md) as flat files stored in this repository. These are read on startup and saved in a memory cache for fast local lookup.

To update these files with new data after elections, run `cd call_server/political_data/data && make clean && make`, and `flask load_political_data`


Code License
------------

See the [license](LICENSE) file for licensing information under the GNU AGPL. This license is applicable to the entire project, sans any 3rd party libraries that may be included.
