"""The first-run endpoints: `setup/status/` (public), `setup/bootstrap/` (public, only while no
developer account exists), `setup/start/` (the developer's session) and `setup/complete/` (the
developer's session). No setup token anywhere — removed by the owner's decision (2026-09-25). See
bootstrap.py for the rules."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import UserSerializer
from apps.accounts.views import set_jwt_cookies
from apps.core.text import normalize_title, to_latin_digits

from . import bootstrap
from .serializers import company_payload


class BootstrapSerializer(serializers.Serializer):
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


class SetupStatusView(APIView):
    """Public: the landing page and the login page ask this to decide what to show."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        response = Response(bootstrap.setup_status())
        response["Cache-Control"] = "no-store"
        return response


class SetupBootstrapView(APIView):
    """Create the **one** developer account on a database that has none — no token, no company, no
    مدیر عامل. Open to anyone only while no developer exists (409 `developer_exists` otherwise: that
    person signs in and continues under `setup/start/`). The rate limit sees every attempt; then the
    payload; only then the database."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(
        ratelimit(key="ip", rate=lambda group, request: settings.SETUP_RATELIMIT_RATE, method="POST", block=True)
    )
    def post(self, request):
        serializer = BootstrapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = bootstrap.bootstrap_developer(
            full_name=data["full_name"],
            national_code=data["national_code"],
            mobile_phone=data["mobile_phone"],
            password=data["password"],
        )
        response = Response({"user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)
        # They just created the account, so they are signed in and the wizard continues under it.
        refresh = RefreshToken.for_user(user)
        set_jwt_cookies(response, str(refresh.access_token), str(refresh))
        get_token(request)
        response["Cache-Control"] = "no-store"
        return response


#: The root's name when the developer just presses «شروع راه‌اندازی»; the wizard's first step
#: («شرکت و حوزه‌ها») opens on it for editing.
DEFAULT_COMPANY_NAME = "شرکت من"


class StartSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class SetupStartView(APIView):
    """`POST /setup/start/` — the developer's one button. Creates the company, the root node and its
    channel; no membership is written here (the developer never sits in the chart)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_developer:
            raise PermissionDenied("راه‌اندازی شرکت را فقط توسعه‌دهنده می‌تواند شروع کند.")
        serializer = StartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = bootstrap.start_company(
            company_name=serializer.validated_data["company_name"].strip() or DEFAULT_COMPANY_NAME
        )
        response = Response({"company": company_payload(company, request)}, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "no-store"
        return response


class SetupCompleteView(APIView):
    """`POST /setup/complete/` — the developer says the chart is drawn. Needs an active lead on the
    company root (a مدیر عامل placed through the «پرسنل» step), not `manage_organization`: the
    مدیر عامل holds that capability too, and finishing setup is the developer's job alone."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_developer:
            raise PermissionDenied("پایان راه‌اندازی را فقط توسعه‌دهنده می‌تواند انجام دهد.")
        bootstrap.complete_setup()
        return Response(bootstrap.setup_status())
