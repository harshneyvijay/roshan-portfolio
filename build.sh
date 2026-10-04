#!/usr/bin/env bash
# Render build step: install, collect static, migrate, create the first admin (only if it doesn't exist yet).
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput || echo "Admin already exists – skipping."
fi
