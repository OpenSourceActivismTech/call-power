# Django + React migration

This directory contains the new application stack for Call Power. It is designed
to run side-by-side with the legacy Flask app while features are ported over in
small slices.

## What is migrated in this slice

- Django project scaffold under `django_app/config`
- Legacy table mappings for campaigns, calls, sessions, scheduled calls, users, targets, CRM sync records, and blocklist records
- Django-managed scheduler metadata for recurring outbound calls and CRM sync timing
- JSON API endpoints for dashboard summary, campaign list/detail, campaign create/update, campaign copy, phone number lookup, and target lookup
- React admin shell in `frontend/` powered by Vite with editable campaign fields, phone-number assignment, target assignment, embed configuration, and CRM sync configuration
- Public Django pages for `/`, `/campaign/<id>/`, legacy `/create` aliases, and campaign embed endpoints
- Twilio call-flow foundation under `callpower/apps/calls/` for outbound call creation, inbound connection entrypoints, TwiML call chaining, and status callbacks backed by the legacy tables
- Twilio schedule prompt and recurring-call subscription flow backed by the Django-managed scheduler
- Django management commands for legacy operational tasks, including scheduler backfill and job execution
- Django CRM sync execution with `sync_call` tracking and scheduler-driven sync runs
- Django political-data providers under `callpower/apps/political_data/` for country data loading, cache-backed lookup, target hydration, and location-based target resolution used by the new Twilio flow

## Current migration boundary

The Django stack now covers the main webhook backbone and the political-data
lookup layer, but it is still not a perfect feature match with Flask.

- US custom-target and US location-based targeting are now the strongest paths in the new stack
- Canada support still depends on the optional `represent` Python package being available
- Legacy third-party embed snippets can now point at the Django-served `/api/campaign/<id>/embed.js` and iframe endpoints
- CRM sync now runs from Django for the legacy `rogue`, `mobilecommons`, and optional `actionkit` integrations
- `actionkit` still depends on the optional `python-actionkit` package being installed in the runtime

## Development

1. Install Python dependencies from `requirements/common.txt`
2. Install frontend dependencies in `frontend/`
3. Start Django:

```bash
python3 manage.py runserver
```

4. Start React:

```bash
cd frontend
npm install
npm run dev
```

The Django admin shell is served at `/admin/`, and in development it loads the
React app from the Vite dev server.

The public site root is served at `/`, public campaign pages at `/campaign/<id>/`,
and legacy call-congress compatibility aliases remain available at `/create`,
`/incoming_call`, and `/call_complete_status`.

## Scheduled jobs

Recurring jobs are now managed by Django instead of Flask RQ.

- Backfill scheduler rows from existing `schedule_call` and `sync_campaign` records:

```bash
python3 manage.py syncscheduledjobs
```

- Run the scheduler loop:

```bash
python3 manage.py runjobs
```

- Run a single scheduler tick:

```bash
python3 manage.py runjobs --once
```

- Run CRM sync immediately for one campaign or all configured campaigns:

```bash
python3 manage.py crmsync 123
python3 manage.py crmsync all
```

## Database compatibility

The Django models in this slice use `managed = False` so Django can read from
the existing schema without trying to recreate or alter the legacy tables. As
more of the application is migrated, we can introduce Django-native migrations
for new tables and selectively take ownership of old ones.
