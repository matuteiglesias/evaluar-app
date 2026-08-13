FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --wheel-dir /wheels ".[ai,queue]"

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=evaluar.config.settings.production
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels
COPY manage.py docker-entrypoint.sh ./
COPY gunicorn.conf.py ./
RUN DJANGO_SETTINGS_MODULE=evaluar.config.settings.static_build \
        python manage.py collectstatic --noinput \
    && test -f "$(DJANGO_SETTINGS_MODULE=evaluar.config.settings.static_build python -c \
        'from django.conf import settings; print(settings.STATIC_ROOT)')/admin/css/base.css" \
    && test -f "$(DJANGO_SETTINGS_MODULE=evaluar.config.settings.static_build python -c \
        'from django.conf import settings; print(settings.STATIC_ROOT)')/staticfiles.json" \
    && chmod +x docker-entrypoint.sh \
    && useradd --create-home evaluar \
    && chown -R evaluar:evaluar /app
USER evaluar
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "evaluar.config.wsgi:application", "--config", "gunicorn.conf.py"]
