"""Cookie-based JWT authentication for VEye V2.

Two responsibilities live here, both called out explicitly in skeleton.md §4:

1. Read the access token from the `access_token` httpOnly cookie instead of
   (or in addition to) an `Authorization: Bearer ...` header, since the
   frontend never sees the raw token — it only holds the httpOnly cookies
   Django sets on login.

2. Reject tokens whose `jti` claim has been placed on the Redis-backed
   blacklist (`blacklist:<jti>`, via django.core.cache.cache / django-redis).
   This is deliberately NOT SimpleJWT's default Postgres `token_blacklist`
   app — see apps/accounts/views.py (refresh/logout) for where entries get
   written, with TTL = the token's remaining lifetime, so the blacklist is
   self-cleaning and never needs a cleanup job.

CSRF: because this authentication class is the DRF-wide default
(config.settings.base.REST_FRAMEWORK), `enforce_csrf()` runs the same
double-submit-cookie check DRF's own SessionAuthentication performs, for
every request this class successfully authenticates a user from a cookie.
That gives every ordinary ViewSet CSRF protection for free on unsafe methods
without per-view decoration. The three auth endpoints that a client calls
*before* holding a valid access-token cookie (login) or that only need the
refresh cookie (refresh/logout) are handled separately with an explicit
`@method_decorator(csrf_protect, name="dispatch")` on refresh/logout in
views.py — see the comment there for why login itself is exempt.
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


def blacklist_key(jti: str) -> str:
    return f"blacklist:{jti}"


def is_blacklisted(jti: str) -> bool:
    return bool(cache.get(blacklist_key(jti)))


def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        ttl_seconds = 1
    cache.set(blacklist_key(jti), True, timeout=ttl_seconds)


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = self._get_raw_token(request)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        self.enforce_csrf(request)

        return user, validated_token

    def _get_raw_token(self, request):
        # Prefer an Authorization header if a client sends one (e.g. tests,
        # service-to-service calls), otherwise fall back to the httpOnly
        # access_token cookie the browser sends automatically.
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                return raw_token
        return request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)

    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)
        jti = validated_token.get("jti")
        if jti and is_blacklisted(jti):
            raise InvalidToken("Token is blacklisted.")
        return validated_token

    def enforce_csrf(self, request):
        """Mirrors rest_framework.authentication.SessionAuthentication's
        double-submit-cookie CSRF check (see module docstring)."""

        def dummy_get_response(request):  # pragma: no cover
            return None

        check = CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied("CSRF Failed: %s" % reason)
