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

# docker-compose.prod.yml builds with REQUIREMENTS=prod (adds gunicorn). A separate, later layer so the
# dev image's cached install above is untouched; for dev builds this step does nothing.
ARG REQUIREMENTS=dev
RUN if [ "$REQUIREMENTS" != "dev" ]; then \
        pip install --no-cache-dir --timeout=120 --retries=10 -r requirements/${REQUIREMENTS}.txt; \
    fi

# Phase 20: pg_dump for the nightly backups (apps/ops), from the PostgreSQL project's own repository so its
# major version matches the server (postgres:16): Debian trixie's own client is 17, whose custom-format dumps
# a version-16 pg_restore cannot read. After the pip layers on purpose: a change here must not invalidate
# their cache (PyPI is not always reachable from the machines that build this image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

# docker-compose.yml supplies the actual `command:` (runserver in dev,
# gunicorn in a prod override) — this CMD is just a sane default.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
