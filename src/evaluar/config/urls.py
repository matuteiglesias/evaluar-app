from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from evaluar.common.views import live, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("courses/", include("evaluar.courses.urls")),
    path("internal/tutoring/", include("evaluar.tutoring.worker_urls")),
    path("tutoring/", include("evaluar.tutoring.urls")),
    path("support/", include("evaluar.support.urls")),
    path("health/live", live, name="health-live"),
    path("health/ready", ready, name="health-ready"),
    path("", RedirectView.as_view(pattern_name="courses:list", permanent=False)),
]
