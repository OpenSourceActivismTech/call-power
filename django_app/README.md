# Django + React migration

This directory contains the new application stack for Call Power. It is designed
to run side-by-side with the legacy Flask app while features are ported over in
small slices.

## What is migrated in this slice

- Django project scaffold under `django_app/config`
- Legacy table mappings for campaigns, calls, sessions, scheduled calls, users, targets, CRM sync records, and blocklist records
- JSON API endpoints for dashboard summary, campaign list/detail, campaign create/update, campaign copy, phone number lookup, and target lookup
- React admin shell in `frontend/` powered by Vite with editable campaign fields, phone-number assignment, target assignment, embed configuration, and CRM sync configuration
- Twilio call-flow foundation under `callpower/apps/calls/` for outbound call creation, inbound connection entrypoints, TwiML call chaining, and status callbacks backed by the legacy tables
- Django political-data providers under `callpower/apps/political_data/` for country data loading, cache-backed lookup, target hydration, and location-based target resolution used by the new Twilio flow

## Current migration boundary

The Django stack now covers the main webhook backbone and the political-data
lookup layer, but it is still not a perfect feature match with Flask.

- US custom-target and US location-based targeting are now the strongest paths in the new stack
- Canada support still depends on the optional `represent` Python package being available
- Legacy dynamic audio selection and recording management still live in Flask
- Built-in Django admin/auth/session migrations are still unapplied unless you run `python3 manage.py migrate`

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

## Database compatibility

The Django models in this slice use `managed = False` so Django can read from
the existing schema without trying to recreate or alter the legacy tables. As
more of the application is migrated, we can introduce Django-native migrations
for new tables and selectively take ownership of old ones.
