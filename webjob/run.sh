#!/usr/bin/env bash
set -e

cd /home/site/wwwroot
# Run the Django management command
python manage.py check_deadlines
