from django.db import connection
from django.http import JsonResponse


def live(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # readiness must translate infrastructure errors to HTTP 503
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
