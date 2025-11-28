#!/bin/bash

# Log start
echo "Starting startup script..." >> /home/LogFiles/startup.log

# Update apt and install required system libraries for WeasyPrint
echo "Installing system dependencies..." >> /home/LogFiles/startup.log
apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libgobject-2.0-0 \
    python3-gi \
    --no-install-recommends >> /home/LogFiles/startup.log 2>&1

# Activate Python virtual environment
echo "Activating virtual environment..." >> /home/LogFiles/startup.log
source /home/site/wwwroot/antenv/bin/activate

# Install Python requirements just in case (optional)
# pip install -r /home/site/wwwroot/requirements.txt

# Start Gunicorn server
echo "Starting Django with Gunicorn..." >> /home/LogFiles/startup.log
exec gunicorn LMS.wsgi:application --bind=0.0.0.0:8000 --workers=4 >> /home/LogFiles/startup.log 2>&1
