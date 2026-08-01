import json
import logging
from uuid import UUID

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.module_loading import import_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TutoringAttempt, TutoringSubmission
from .services import mark_terminal_failure, run_submission

logger = logging.getLogger(__name__)


def _verify_oidc_token(token: str) -> dict:
    from google.auth.transport import requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(
        token, requests.Request(), audience=settings.TUTORING_TASK_AUDIENCE
    )


def _authorized(request) -> bool:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not settings.TUTORING_TASK_AUDIENCE:
        return False
    try:
        claims = _verify_oidc_token(authorization.removeprefix("Bearer "))
    except Exception:
        return False
    expected_email = settings.TUTORING_TASK_SERVICE_ACCOUNT
    return bool(claims.get("email") == expected_email and claims.get("email_verified", False))


@csrf_exempt
@require_POST
def run_worker(request):
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        body = json.loads(request.body)
        if set(body) != {"submission_id"}:
            raise ValueError
        submission_id = UUID(body["submission_id"])
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    factory_path = getattr(settings, "TUTORING_MODEL_FACTORY", "")
    if not factory_path:
        return JsonResponse({"error": "worker_not_configured"}, status=503)
    factory = import_string(factory_path)()
    submission = TutoringSubmission.objects.select_related("prompt_version").get(pk=submission_id)
    model = factory.for_prompt(submission.prompt_version)
    response = run_submission(submission_id, model)
    submission = TutoringSubmission.objects.get(pk=submission_id)
    retry_count = int(request.headers.get("X-CloudTasks-TaskRetryCount", "0"))
    max_attempts = settings.TUTORING_TASK_MAX_ATTEMPTS
    logger.info(
        "tutoring.worker_attempt",
        extra={
            "submission_id": str(submission_id),
            "delivery_attempt": retry_count + 1,
            "status": submission.status,
        },
    )
    if response is not None or submission.status in (
        TutoringSubmission.Status.SUCCEEDED,
        TutoringSubmission.Status.FAILED,
        TutoringSubmission.Status.CANCELLED,
    ):
        return HttpResponse(status=204)
    latest_attempt = submission.attempts.order_by("-number").first()
    if latest_attempt and latest_attempt.status == TutoringAttempt.Status.PROVIDER_SUCCEEDED:
        logger.error(
            "tutoring.ambiguous_attempt",
            extra={
                "submission_id": str(submission_id),
                "attempt_id": str(latest_attempt.id),
            },
        )
        return HttpResponse(status=204)
    if retry_count + 1 >= max_attempts:
        mark_terminal_failure(submission_id)
        return HttpResponse(status=204)
    return JsonResponse({"error": "retryable_failure"}, status=503)
