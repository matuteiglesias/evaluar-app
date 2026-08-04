from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse


def live(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        if MigrationExecutor(connection).migration_plan(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        ):
            return JsonResponse({"status": "unavailable", "reason": "schema"}, status=503)
    except Exception:  # readiness must translate infrastructure errors to HTTP 503
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
