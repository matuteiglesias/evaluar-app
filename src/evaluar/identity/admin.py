from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AuditEvent, CourseMembership, PendingCourseEnrollment, User

admin.site.register(User, UserAdmin)
admin.site.register(CourseMembership)
admin.site.register(PendingCourseEnrollment)
admin.site.register(AuditEvent)
