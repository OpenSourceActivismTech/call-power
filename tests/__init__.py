import os
import sys

import django


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "django_app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
