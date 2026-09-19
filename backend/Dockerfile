FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg[binary] ships its own wheel, but libpq-dev/build-essential cover
# any source-build fallback + Pillow's image codecs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev libjpeg62-turbo-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --no-cache-dir --timeout=120 --retries=10 -r requirements/dev.txt

COPY . .

EXPOSE 8000

# docker-compose.yml supplies the actual `command:` (runserver in dev,
# gunicorn in a prod override) — this CMD is just a sane default.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
