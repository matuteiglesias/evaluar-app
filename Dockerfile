FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY llm ./llm
COPY models ./models
COPY routes ./routes
COPY services ./services
COPY src ./src
RUN pip wheel --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.production
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY manage.py docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && useradd --create-home evaluar && chown -R evaluar:evaluar /app
USER evaluar
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--chdir", "src/evaluar", "--bind", "0.0.0.0:8000"]
