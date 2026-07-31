from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from common.views import live, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("courses/", include("courses.urls")),
    path("health/live", live, name="health-live"),
    path("health/ready", ready, name="health-ready"),
    path("", RedirectView.as_view(pattern_name="courses:list", permanent=False)),
]
