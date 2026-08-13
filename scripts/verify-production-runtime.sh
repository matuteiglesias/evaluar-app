#!/bin/sh
# Exercise the same final-image contract locally and in CI. No provider API is called.
set -eu

IMAGE=${IMAGE:-evaluar-app:production-runtime}
PORT=${PORT:-8765}
NETWORK="evaluar-runtime-$$"
DB="evaluar-runtime-db-$$"
WEB="evaluar-runtime-web-$$"
COMMON_ENV="--network $NETWORK -e DATABASE_URL=postgresql://evaluar:evaluar@$DB:5432/evaluar -e DJANGO_SECRET_KEY=runtime-verification-only-secret -e DJANGO_ALLOWED_HOSTS=localhost -e DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost -e GOOGLE_CLIENT_ID=verification-placeholder -e GOOGLE_CLIENT_SECRET=verification-placeholder"

cleanup() {
    docker rm -f "$WEB" "$DB" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if [ "${SKIP_BUILD:-0}" != 1 ]; then
    docker build -t "$IMAGE" .
fi
docker network create "$NETWORK" >/dev/null
docker run -d --name "$DB" --network "$NETWORK" \
    -e POSTGRES_DB=evaluar -e POSTGRES_USER=evaluar -e POSTGRES_PASSWORD=evaluar \
    postgres:16-alpine >/dev/null
until docker exec "$DB" pg_isready -U evaluar >/dev/null 2>&1; do sleep 1; done

# Starting the web image cannot initialize the database. Liveness works; readiness must not.
# shellcheck disable=SC2086
docker run -d --name "$WEB" $COMMON_ENV -e PORT="$PORT" -p "$PORT:$PORT" "$IMAGE" >/dev/null
for attempt in $(seq 1 30); do
    if curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:$PORT/health/live" >/dev/null; then break; fi
    [ "$attempt" -lt 30 ] || { docker logs "$WEB"; exit 1; }
    sleep 1
done
if curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:$PORT/health/ready" >/dev/null 2>&1; then
    echo "readiness unexpectedly succeeded before the separate migration command" >&2
    exit 1
fi
if docker exec "$DB" psql -U evaluar -d evaluar -tAc \
    "select to_regclass('public.django_migrations')" | grep -q django_migrations; then
    echo "web startup silently created migration state" >&2
    exit 1
fi
docker rm -f "$WEB" >/dev/null

# Migration is an explicit release action against the exact candidate image.
# shellcheck disable=SC2086
docker run --rm $COMMON_ENV "$IMAGE" python manage.py migrate --noinput

# Prove the non-default PORT, both probes, and WhiteNoise's final-image asset.
# shellcheck disable=SC2086
docker run -d --name "$WEB" $COMMON_ENV -e PORT="$PORT" -p "$PORT:$PORT" "$IMAGE" >/dev/null
for attempt in $(seq 1 30); do
    if curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:$PORT/health/ready" >/dev/null; then break; fi
    [ "$attempt" -lt 30 ] || { docker logs "$WEB"; exit 1; }
    sleep 1
done
curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:$PORT/health/live" >/dev/null
curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:$PORT/health/ready" >/dev/null
curl -fsS -H 'X-Forwarded-Proto: https' \
    "http://localhost:$PORT/static/admin/css/base.css" | grep -q -- '--primary'
echo "Production runtime verified on non-default PORT=$PORT."
