from django.urls import path
from . import views

app_name = "courses"
urlpatterns = [
    path("", views.course_list, name="list"),
    path("<slug:course_slug>/", views.exercise_list, name="exercises"),
    path(
        "<slug:course_slug>/<slug:exercise_slug>/v<int:version_number>/",
        views.exercise_version,
        name="version",
    ),
]
