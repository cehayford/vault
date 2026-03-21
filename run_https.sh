#!/usr/bin/env bash
# Run Django dev server with HTTPS (stops "HTTPS but it only supports HTTP" errors).
# First run creates devserver.crt + devserver.key; accept the browser warning once.
cd "$(dirname "$0")"
python manage.py runserver_plus 0.0.0.0:8000 --cert-file devserver.crt
