#!/usr/bin/env python3
import os
import sys


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "django_app"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
