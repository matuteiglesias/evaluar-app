from django.urls import path
from . import views

app_name = "support"
urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("teacher/", views.teacher_dashboard, name="teacher-dashboard"),
    path("new/exercise/<uuid:exercise_version_id>/", views.ticket_create, name="create"),
    path(
        "new/submission/<uuid:submission_id>/",
        views.ticket_create_from_submission,
        name="create-from-submission",
    ),
    path(
        "new/response/<uuid:response_id>/",
        views.ticket_create_from_response,
        name="create-from-response",
    ),
    path("<uuid:ticket_id>/", views.ticket_detail, name="detail"),
    path("<uuid:ticket_id>/messages/", views.message_create, name="message-create"),
    path("<uuid:ticket_id>/claim/", views.claim, name="claim"),
    path("<uuid:ticket_id>/action/", views.action, name="action"),
]
