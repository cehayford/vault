@echo off
REM Run Django dev server with HTTPS (stops "HTTPS but it only supports HTTP" errors).
REM First run creates devserver.crt + devserver.key; accept the browser warning once.
cd /d "%~dp0"
python manage.py runserver_plus 0.0.0.0:8000 --cert-file devserver.crt
pause
