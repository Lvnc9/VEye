"""The first-run endpoints: `setup/status/` (public), `setup/bootstrap/` (setup token) and
`setup/complete/` (the new مدیر عامل's session). See bootstrap.py for the rules."""
import hmac

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Capability
from apps.accounts.serializers import UserSerializer
from apps.accounts.views import set_jwt_cookies
from apps.core.permissions import capability_required
from apps.core.text import normalize_title, to_latin_digits

from . import bootstrap
from .serializers import company_payload

SETUP_TOKEN_HEADER = "HTTP_X_VEYE_SETUP_TOKEN"  # X-VEYE-Setup-Token, as Django's META spells it


class SetupDisabled(APIException):
    """503, not 403: a deployment with no token configured has no setup door at all. A 403 would
    tell an attacker "the door exists, keep guessing"."""

    status_code = 503
    default_detail = "راه‌اندازی اولیه در این استقرار فعال نیست."
    default_code = "setup_disabled"


def require_setup_token(request) -> None:
    """The token travels only in a header — never a query string, never echoed, never logged.
    Both sides are encoded first so a non-ASCII value cannot raise, and compared in constant time."""
    configured = settings.SETUP_TOKEN
    if not configured:
        raise SetupDisabled()
    supplied = request.META.get(SETUP_TOKEN_HEADER, "")
    if not hmac.compare_digest(supplied.encode("utf-8"), configured.encode("utf-8")):
        raise PermissionDenied("توکن راه‌اندازی نادرست است.")


class ManagerSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    national_code = serializers.CharField(max_length=32)
    mobile_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_full_name(self, value):
        return normalize_title(value)

    def validate_national_code(self, value):
        # Persian digits become ASCII, so the account can be signed into with either keyboard
        # once the login page normalises the same way (slice 7.5).
        code = "".join(to_latin_digits(value).split())
        if not code:
            raise serializers.ValidationError("کد ملی نمی‌تواند خالی باشد.")
        return code

    def validate_mobile_phone(self, value):
        return "".join(to_latin_digits(value).split())

    def validate(self, attrs):
        # Django's validators, in Persian (LANGUAGE_CODE=fa): length, common, all-digits, and
        # similarity to the name / national code.
        from apps.accounts.models import User

        candidate = User(national_code=attrs["national_code"], full_name=attrs["full_name"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class BootstrapSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    manager = ManagerSerializer(required=False)
    existing_manager_national_code = serializers.CharField(max_length=32, required=False)

    def validate(self, attrs):
        if ("manager" in attrs) == ("existing_manager_national_code" in attrs):
            raise serializers.ValidationError(
                {"manager": ["یا مشخصات مدیر عامل تازه، یا کد ملی یک مدیر عامل موجود را بفرستید (فقط یکی)."]}
            )
        if "existing_manager_national_code" in attrs:
            attrs["existing_manager_national_code"] = "".join(
                to_latin_digits(attrs["existing_manager_national_code"]).split()
            )
        return attrs


class SetupStatusView(APIView):
    """Public: the login page asks this to decide between the sign-in form and «شروع راه‌اندازی»."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        response = Response(bootstrap.setup_status())
        response["Cache-Control"] = "no-store"
        return response


class SetupBootstrapView(APIView):
    """Create the company and its مدیر عامل on a fresh database.

    Order matters: the rate limit sees every attempt (a wrong token counts), then 503 if setup is
    off, then 403 for a wrong token, then the payload, and only then the database."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(
        ratelimit(key="ip", rate=lambda group, request: settings.SETUP_RATELIMIT_RATE, method="POST", block=True)
    )
    def post(self, request):
        require_setup_token(request)
        serializer = BootstrapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        manager = data.get("manager")
        result = bootstrap.bootstrap(
            company_name=data["company_name"],
            manager=dict(manager) if manager else None,
            existing_manager_national_code=data.get("existing_manager_national_code"),
        )

        body = {
            "company": company_payload(result.company, request),
            "user": UserSerializer(result.user).data,
            "logged_in": result.created_user,
        }
        response = Response(body, status=status.HTTP_201_CREATED)
        if result.created_user:
            # They just proved the token by creating the account, so they are signed in — the wizard
            # continues under their session. A *promoted* account gets no session: the setup token
            # plus a national code must never be a login; they sign in with their own password.
            refresh = RefreshToken.for_user(result.user)
            set_jwt_cookies(response, str(refresh.access_token), str(refresh))
            get_token(request)
        response["Cache-Control"] = "no-store"
        return response


class SetupCompleteView(APIView):
    """`POST /setup/complete/` — the manager says the chart is drawn."""

    permission_classes = [IsAuthenticated, capability_required(Capability.MANAGE_ORGANIZATION)]

    def post(self, request):
        bootstrap.complete_setup()
        return Response(bootstrap.setup_status())
