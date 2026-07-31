from django.contrib import admin
from .models import ContentPublication, Course, Exercise, ExerciseVersion

admin.site.register((Course, Exercise, ContentPublication, ExerciseVersion))
