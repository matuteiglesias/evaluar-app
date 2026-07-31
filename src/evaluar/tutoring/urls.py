from django.urls import path

from . import student_views

app_name = "tutoring"

urlpatterns = [
    path("submit/<uuid:version_id>/", student_views.submit, name="submit"),
    path("submissions/<uuid:submission_id>/", student_views.submission, name="submission"),
    path("submissions/<uuid:submission_id>/status", student_views.status, name="status"),
    path("responses/<uuid:response_id>/feedback", student_views.feedback, name="feedback"),
    path("courses/<slug:course_slug>/failed/", student_views.failed_jobs, name="failed-jobs"),
    path(
        "courses/<slug:course_slug>/failed/<uuid:submission_id>/requeue",
        student_views.requeue_failed_job,
        name="requeue-failed-job",
    ),
]
