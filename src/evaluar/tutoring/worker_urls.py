from django.urls import path

from .views import run_worker

app_name = "tutoring-worker"

urlpatterns = [path("run", run_worker, name="run")]
