from django.conf import settings
from django.http import Http404


class FeatureSafetyMiddleware:
    """Make disabled feature HTTP surfaces indistinguishable from absent routes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith(("/tutoring/", "/internal/tutoring/")) and not settings.TUTORING_ENABLED:
            raise Http404
        if path.startswith("/support/") and not settings.SUPPORT_ENABLED:
            raise Http404
        return self.get_response(request)
