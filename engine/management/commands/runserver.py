"""
Override runserver: HTTPS on 8443 + HTTP redirect on 8000.
So http://127.0.0.1:8000/ redirects to https://127.0.0.1:8443/ and works.
"""
import os
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

HTTPS_PORT = 8443
HTTP_REDIRECT_PORT = 8000


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        host = self.headers.get("Host", "127.0.0.1").split(":")[0]
        location = f"https://{host}:{HTTPS_PORT}{self.path}"
        self.send_response(301)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def run_http_redirect():
    try:
        server = HTTPServer(("127.0.0.1", HTTP_REDIRECT_PORT), RedirectHandler)
        server.serve_forever()
    except OSError:
        pass


class Command(BaseCommand):
    help = (
        f"Run HTTPS on {HTTPS_PORT}; HTTP on {HTTP_REDIRECT_PORT} redirects to HTTPS. "
        "Use http://127.0.0.1:8000 or https://127.0.0.1:8443"
    )

    def handle(self, *args, **options):
        try:
            from django_extensions.management.commands.runserver_plus import Command as RunserverPlusCommand
        except ImportError:
            self.stderr.write(
                self.style.ERROR(
                    "Install django-extensions. Then: python manage.py runserver_plus 0.0.0.0:8443 --cert-file devserver.crt"
                )
            )
            return
        base_dir = Path(settings.BASE_DIR)
        cert_file = base_dir / "devserver.crt"
        if not cert_file.exists():
            self.stdout.write(
                self.style.WARNING("First run may create devserver.crt and devserver.key in project root.")
            )
        try:
            t = threading.Thread(target=run_http_redirect, daemon=True)
            t.start()
            self.stdout.write(
                self.style.SUCCESS(
                    f"HTTP redirect: http://127.0.0.1:{HTTP_REDIRECT_PORT} -> https://127.0.0.1:{HTTPS_PORT}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not start HTTP redirect on {HTTP_REDIRECT_PORT}: {e}"))
        # Run HTTPS server on 8443
        cmd = RunserverPlusCommand()
        cmd.run_from_argv(
            [os.sys.argv[0], "runserver_plus", f"0.0.0.0:{HTTPS_PORT}", f"--cert-file={cert_file}"]
        )
