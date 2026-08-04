from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError

from .models import HumanHelpTicket, TicketAssignment, TicketEvent, TicketMessage
from .services import cancel_ticket, resolve_ticket, start_ticket, wait_for_student


class TicketAssignmentInline(admin.TabularInline):
    model = TicketAssignment
    extra = 0
    can_delete = False
    readonly_fields = (
        "teacher",
        "assigned_by",
        "status",
        "assigned_at",
        "accepted_at",
        "released_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "actor", "from_status", "to_status", "metadata", "created_at")


@admin.register(HumanHelpTicket)
class HumanHelpTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "student", "priority", "status", "created_at")
    list_filter = ("course", "priority", "status")
    readonly_fields = (
        "course",
        "student",
        "exercise_version",
        "tutoring_submission",
        "tutoring_response",
        "idempotency_key",
        "status",
        "created_at",
        "updated_at",
        "resolved_at",
    )
    inlines = (TicketAssignmentInline, TicketEventInline)
    actions = ("start_selected", "wait_selected", "resolve_selected", "cancel_selected")

    def _run_service(self, request, queryset, service):
        changed = 0
        for ticket in queryset:
            try:
                service(ticket=ticket, actor=request.user)
            except (PermissionDenied, ValidationError) as exc:
                self.message_user(request, f"{ticket.id}: {exc}", level="error")
            else:
                changed += 1
        self.message_user(request, f"Updated {changed} ticket(s).")

    @admin.action(description="Start selected assigned tickets")
    def start_selected(self, request, queryset):
        self._run_service(request, queryset, start_ticket)

    @admin.action(description="Wait for student on selected tickets")
    def wait_selected(self, request, queryset):
        self._run_service(request, queryset, wait_for_student)

    @admin.action(description="Resolve selected tickets")
    def resolve_selected(self, request, queryset):
        self._run_service(request, queryset, resolve_ticket)

    @admin.action(description="Cancel selected open or assigned tickets")
    def cancel_selected(self, request, queryset):
        self._run_service(request, queryset, cancel_ticket)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "visibility", "created_at")
    readonly_fields = ("ticket", "author", "body", "visibility", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketAssignment)
class TicketAssignmentAdmin(admin.ModelAdmin):
    readonly_fields = (
        "ticket",
        "teacher",
        "assigned_by",
        "status",
        "assigned_at",
        "accepted_at",
        "released_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
