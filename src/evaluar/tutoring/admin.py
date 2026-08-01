from django.contrib import admin, messages

from .models import PromptVersion, TutoringAttempt, TutoringResponse, TutoringSubmission
from .services import InvalidTransition, requeue_submission


@admin.action(description="Requeue selected failed tutoring submissions")
def requeue_failed(modeladmin, request, queryset):
    requeued = 0
    for submission in queryset:
        try:
            requeue_submission(submission.id)
        except InvalidTransition:
            continue
        requeued += 1
    modeladmin.message_user(request, f"Requeued {requeued} submission(s).", messages.SUCCESS)


@admin.register(TutoringSubmission)
class TutoringSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at", "updated_at")
    list_filter = ("status",)
    actions = (requeue_failed,)


@admin.register(PromptVersion)
class PromptVersionAdmin(admin.ModelAdmin):
    list_display = ("public_id", "version", "status", "created_at", "published_at")
    readonly_fields = (
        "id",
        "public_id",
        "version",
        "system_instructions",
        "response_schema_version",
        "model_policy",
        "temperature",
        "max_output_tokens",
        "checksum",
        "status",
        "created_at",
        "published_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(TutoringAttempt)
admin.site.register(TutoringResponse)
