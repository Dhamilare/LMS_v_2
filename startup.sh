
#!/bin/bash
set -e

echo "Starting startup script..." >> /home/LogFiles/startup.log

apt-get update && apt-get install -y \
    libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libgobject-2.0-0 python3-gi \
    --no-install-recommends >> /home/LogFiles/startup.log 2>&1

echo "Activating virtual environment..." >> /home/LogFiles/startup.log
. /home/site/wwwroot/antenv/bin/activate

echo "Starting Django with Gunicorn..." >> /home/LogFiles/startup.log
exec gunicorn LMS.wsgi:application --bind=0.0.0.0:8000 --workers=4 >> /home/LogFiles/startup.log 2>&1
