from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import ProtectedError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as simplejwt_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from django.conf import settings

from apps.core.exceptions import ConflictError
from apps.core.permissions import HasCapability

from .authentication import blacklist_jti, is_blacklisted
from .models import Capability, User
from .serializers import LoginSerializer, PlacementSerializer, UserSerializer

# NOTE on CSRF (see also apps/accounts/authentication.py docstring):
# - LoginView is deliberately left without an explicit csrf_protect: at
#   login time the client holds no valid access_token cookie yet, so there
#   is no authenticated session for a cross-site request to hijack. Django's
#   CsrfViewMiddleware stays enabled project-wide regardless.
# - RefreshView/LogoutView act on the refresh_token cookie alone (no access
#   token required), so CookieJWTAuthentication.enforce_csrf() never runs
#   for them; they get an explicit @method_decorator(csrf_protect) instead.
# - Every other view in the project authenticates via CookieJWTAuthentication,
#   whose enforce_csrf() (mirroring DRF's SessionAuthentication) covers all
#   of them uniformly for POST/PUT/PATCH/DELETE.
from django.views.decorators.csrf import csrf_protect


def _cookie_kwargs(max_age: int) -> dict:
    return dict(
        max_age=max_age,
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite=settings.JWT_COOKIE_SAMESITE,
        path=settings.JWT_COOKIE_PATH,
    )


def set_jwt_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(settings.JWT_ACCESS_COOKIE_NAME, access_token, **_cookie_kwargs(access_lifetime))
    response.set_cookie(settings.JWT_REFRESH_COOKIE_NAME, refresh_token, **_cookie_kwargs(refresh_lifetime))


def _clear_jwt_cookies(response: Response) -> None:
    response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME, path=settings.JWT_COOKIE_PATH)
    response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path=settings.JWT_COOKIE_PATH)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate=settings.LOGIN_RATELIMIT_RATE, method="POST", block=True))
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            national_code=serializer.validated_data["national_code"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "کد ملی یا رمز عبور اشتباه است."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response(session_user_data(user), status=status.HTTP_200_OK)
        set_jwt_cookies(response, str(access), str(refresh))
        # Forces CsrfViewMiddleware to emit a fresh, readable csrftoken cookie
        # on this response (skeleton.md §4).
        get_token(request)
        return response


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(csrf_protect)
    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            return Response({"detail": "Refresh token missing."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(raw_refresh)
        except TokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        old_jti = old_refresh["jti"]
        if is_blacklisted(old_jti):
            return Response({"detail": "Refresh token has been blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(**{UserModel.USERNAME_FIELD: old_refresh[simplejwt_settings.USER_ID_CLAIM]})
        except UserModel.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"detail": "User inactive."}, status=status.HTTP_401_UNAUTHORIZED)

        new_refresh = RefreshToken.for_user(user)
        new_access = new_refresh.access_token

        # Rotate + immediately blacklist the old refresh token (reuse
        # detection), TTL = its remaining lifetime so Redis self-cleans.
        ttl = int(old_refresh["exp"] - timezone.now().timestamp())
        blacklist_jti(old_jti, ttl)

        response = Response({"detail": "Refreshed."}, status=status.HTTP_200_OK)
        set_jwt_cookies(response, str(new_access), str(new_refresh))
        return response


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(csrf_protect)
    def post(self, request):
        now_ts = timezone.now().timestamp()
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        raw_access = request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)

        for raw_token, token_cls in ((raw_refresh, RefreshToken), (raw_access, AccessToken)):
            if not raw_token:
                continue
            try:
                token = token_cls(raw_token)
            except TokenError:
                continue
            ttl = int(token["exp"] - now_ts)
            blacklist_jti(token["jti"], ttl)

        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        _clear_jwt_cookies(response)
        return response


def session_user_data(user) -> dict:
    """The signed-in user as the app shell reads it: the serializer's fields, with `capabilities` including
    what the org chart grants for documents (a مسئول may write; a مسئول of a واحد or حوزه may also confirm;
    only the مدیر عامل approves — documents/authority.py). The personnel directory keeps the plain
    roll-based list: computing a lead query for every row of a directory would be wasteful, and it
    describes the سمت, not the person's place in the chart."""
    from apps.documents.authority import effective_capabilities  # not at import time: accounts is imported first

    data = UserSerializer(user).data
    data["capabilities"] = sorted(effective_capabilities(user))
    return data


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Imported here so accounts never depends on the org app at import time.
        from apps.organization.me import org_context

        return Response({**session_user_data(request.user), **org_context(request.user, request)})


class PersonnelViewSet(viewsets.ModelViewSet):
    """CRUD over personnel.

    Any authenticated user can browse the directory (the document register
    needs to resolve names and سمت for its columns), but creating or editing
    personnel requires MANAGE_PERSONNEL — i.e. کارفرمایی.
    """

    queryset = User.objects.all().order_by("national_code")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_PERSONNEL

    def _protect_developer(self, person) -> None:
        """Only the developer may change or delete the developer account. Without this, anyone with
        manage_personnel (a مدیر عامل) could reset its password or deactivate it and lock the
        technical account out."""
        if person.is_developer and person.pk != self.request.user.pk:
            raise PermissionDenied(
                "حساب توسعه‌دهنده را فقط خود توسعه‌دهنده می‌تواند تغییر دهد یا حذف کند.",
                code="developer_protected",
            )

    def create(self, request, *args, **kwargs):
        """Register a person and, optionally, place them in the org chart in one request
        (ADR-010 §B). Placement used to be a second `POST /org/memberships/` that could fail on
        its own, leaving an unplaced account behind; now either both happen or neither does.

        Order matters: validate the user fields, then resolve the node and check
        `can_manage_members` on it *before* creating anything, so a caller who may register
        personnel but not manage that node's members learns that without side effects. Only
        after that do the user and the membership get created, together, in one transaction.

        `apps.organization` is imported here, not at module level: accounts is the lower-level
        app (organization imports it), and a module-level import the other way round would be a
        real circular-import risk the moment organization needs something from accounts at
        import time (MeView.get above does the same for `org_context`, for the same reason).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        placement_data = request.data.get("placement")
        node = None
        placement = None
        if placement_data:
            placement_serializer = PlacementSerializer(data=placement_data)
            placement_serializer.is_valid(raise_exception=True)
            placement = placement_serializer.validated_data

            from apps.organization.access import access_for
            from apps.organization.models import OrgNode

            try:
                node = OrgNode.objects.get(pk=placement["node"])
            except OrgNode.DoesNotExist:
                raise NotFound("گره سازمانی یافت نشد.")
            if not access_for(request).can_manage_members(node):
                raise PermissionDenied(
                    "شما اجازهٔ افزودن عضو به این گره یا گره‌های بالادستی آن را ندارید."
                )

        membership = None
        with transaction.atomic():
            self.perform_create(serializer)
            if node is not None:
                from apps.organization import memberships

                membership = memberships.add_membership(
                    user=serializer.instance,
                    node=node,
                    is_lead=placement["is_lead"],
                    position_label=placement["position_label"],
                    added_by=request.user,
                )

        data = dict(serializer.data)
        if membership is not None:
            from apps.organization.serializers import MembershipSerializer

            data["membership"] = MembershipSerializer(membership).data

        headers = self.get_success_headers(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        # Before validation, so a refused caller learns nothing from field errors.
        self._protect_developer(self.get_object())
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        person = self.get_object()
        self._protect_developer(person)
        # Memberships (apps/organization) also reference a person with PROTECT. Say so
        # here, with the count, rather than let the handler below blame documents.
        # (`memberships` is that app's reverse accessor; accounts imports nothing from it.)
        membership_count = person.memberships.count()
        if membership_count:
            raise ConflictError(
                "این شخص عضو ساختار سازمانی است و حذف نمی‌شود. ابتدا عضویت‌های او را حذف کنید یا حساب او را غیرفعال کنید.",
                code="user_has_memberships",
                memberships=membership_count,
            )
        # Projects reference their creator and their members with PROTECT too.
        project_count = person.project_memberships.count() + person.created_projects.count()
        if project_count:
            raise ConflictError(
                "این شخص در پروژه‌ها حضور دارد و حذف نمی‌شود. ابتدا او را از پروژه‌ها خارج کنید یا حساب او را غیرفعال کنید.",
                code="user_has_projects",
                projects=project_count,
            )
        # A temporary cover (Phase 16) references the delegate with PROTECT as well; without this the
        # handler below would blame documents for it.
        delegation_count = person.delegations_received.count()
        if delegation_count:
            raise ConflictError(
                "این شخص جانشین موقت یک مسئول بوده است و حذف نمی‌شود. به‌جای حذف، حساب او را غیرفعال کنید.",
                code="user_has_delegations",
                delegations=delegation_count,
            )
        # Quality records (Phase 18) reference their reporter, their action assignees and an audit's
        # lead auditor with PROTECT: they are never deleted, so neither is the person who filed, was
        # given or led one.
        quality_count = (
            person.reported_nonconformances.count()
            + person.assigned_corrective_actions.count()
            + person.led_audits.count()
        )
        if quality_count:
            raise ConflictError(
                "این شخص در سوابق کیفیت (عدم‌انطباق، اقدام اصلاحی یا ممیزی) حضور دارد و حذف نمی‌شود. به‌جای حذف، حساب او را غیرفعال کنید.",
                code="user_has_quality_records",
                records=quality_count,
            )
        # Documents reference their author with on_delete=PROTECT, so removing
        # someone who ever authored one would otherwise be an unhandled 500. The
        # right way to retire a person is to deactivate them (is_active=false),
        # which keeps every document's history attributable.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise ConflictError(
                "این شخص مستند ثبت کرده است و حذف نمی‌شود. به‌جای حذف، حساب او را غیرفعال کنید.",
                code="user_has_documents",
            )

    @action(detail=True, methods=["get"])
    def title(self, request, pk=None):
        user = self.get_object()
        return Response({"title": user.title})
