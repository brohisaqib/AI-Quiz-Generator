"""
Production WSGI entrypoint.

This module is used by Gunicorn (and other WSGI servers) to serve the
Flask application in production. It is intentionally minimal.

Usage (inside Docker or on EC2):
    gunicorn -w 4 -b 0.0.0.0:5000 --timeout 300 wsgi:app

Local dev (optional — python app.py is preferred for local):
    FLASK_ENV=development gunicorn -w 1 -b 127.0.0.1:5000 wsgi:app
"""

from app import create_app

# Gunicorn discovers this 'app' object at module level.
app = create_app()
