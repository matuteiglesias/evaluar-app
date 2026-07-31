"""Narrow identity-provider boundary around the legacy Authlib Google client."""

from dataclasses import dataclass

import requests
from authlib.integrations.base_client.errors import OAuthError
from flask import current_app

from main import oauth


class IdentityProviderError(RuntimeError):
    """The external identity exchange failed or returned an invalid identity."""


@dataclass(frozen=True)
class AuthenticatedIdentity:
    subject: str
    email: str
    name: str
    picture: str = ""


class GoogleIdentityProvider:
    def begin(self, redirect_uri):
        return oauth.google.authorize_redirect(
            redirect_uri=redirect_uri, scope="openid email profile"
        )

    def complete(self, timeout):
        try:
            token = oauth.google.authorize_access_token(timeout=timeout)
            if not token or not token.get("access_token"):
                raise IdentityProviderError
            response = oauth.google.get("userinfo", token=token, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not data.get("sub") or not data.get("email"):
                raise IdentityProviderError
            if data.get("email_verified") is not True:
                raise IdentityProviderError
        except (OAuthError, requests.RequestException, ValueError, TypeError) as error:
            raise IdentityProviderError from error
        return AuthenticatedIdentity(
            subject=data["sub"],
            email=data["email"],
            name=data.get("given_name") or data.get("name") or data["email"],
            picture=data.get("picture", ""),
        )


def get_identity_provider():
    return current_app.extensions.get("identity_provider") or GoogleIdentityProvider()
