#!/bin/bash

# Install WeasyPrint system dependencies
apt-get update -y
apt-get install -y \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

# Start the Django app
gunicorn --bind=0.0.0.0:8000 --timeout 600 LMS.wsgi