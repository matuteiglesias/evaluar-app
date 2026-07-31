import hashlib
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import ValidationError


class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Bind allauth's validated Google subject to the local, email-independent identity."""

    def populate_user(self, request, sociallogin, data):
        if sociallogin.account.provider != "google" or not sociallogin.account.uid:
            raise ValidationError("A validated Google OIDC subject is required.")
        user = super().populate_user(request, sociallogin, data)
        subject = sociallogin.account.uid
        user.external_subject = subject
        user.username = f"google_{hashlib.sha256(subject.encode()).hexdigest()[:24]}"
        return user
