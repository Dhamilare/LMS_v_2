# ===== Python Base =====
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# ===== System Dependencies =====
# WeasyPrint + Cairo + Pango + Fonts + LibreOffice (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 libcairo2-dev \
    libpango-1.0-0 libpango1.0-dev \
    libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 libgdk-pixbuf2.0-dev \
    libharfbuzz0b libfribidi0 \
    libjpeg62-turbo libjpeg62-turbo-dev \
    libxml2-dev libxslt1-dev \
    libffi-dev libssl-dev zlib1g-dev \
    fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
    poppler-utils \
    libreoffice-core libreoffice-writer libreoffice-common \
    ca-certificates curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ===== App User =====
RUN useradd -m appuser
WORKDIR /home/appuser/app

# ===== Install Python dependencies =====
COPY --chown=appuser:appuser requirements.txt .
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ===== Copy Project =====
COPY --chown=appuser:appuser . .

# ===== Collect Static Files =====
ENV DJANGO_SETTINGS_MODULE=LMS.settings
RUN python manage.py collectstatic --noinput || true

# Add local bin to PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

USER appuser

EXPOSE 8000

# ===== Start Server =====
CMD ["gunicorn", "LMS.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
