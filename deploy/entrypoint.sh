#!/bin/sh
set -e

# Run database migrations
echo "Running database migrations..."
flask db upgrade

# Start gunicorn production server
echo "Starting backend Gunicorn server..."
exec gunicorn -w 4 -b 0.0.0.0:5000 --timeout 300 --access-logfile - --error-logfile - wsgi:app
