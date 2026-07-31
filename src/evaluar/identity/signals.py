from allauth.account.signals import user_logged_in
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import AuditEvent, CourseMembership


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) if request else None


@receiver(user_logged_in)
def audit_sign_in(request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        subject_user=user,
        event=AuditEvent.Event.SIGN_IN,
        ip_address=_client_ip(request),
    )


@receiver(post_save, sender=CourseMembership)
def audit_membership_save(sender, instance, created, **kwargs):
    AuditEvent.objects.create(
        subject_user=instance.user,
        course=instance.course,
        event=AuditEvent.Event.MEMBERSHIP_CREATED
        if created
        else AuditEvent.Event.MEMBERSHIP_CHANGED,
        metadata={"role": instance.role, "status": instance.status},
    )


@receiver(post_delete, sender=CourseMembership)
def audit_membership_delete(sender, instance, **kwargs):
    AuditEvent.objects.create(
        subject_user=instance.user,
        course=instance.course,
        event=AuditEvent.Event.MEMBERSHIP_DELETED,
        metadata={"role": instance.role, "status": instance.status},
    )
