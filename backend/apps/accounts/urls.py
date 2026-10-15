from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LoginView,
    LogoutOthersView,
    LogoutView,
    MeView,
    PasswordChangeView,
    PersonnelViewSet,
    RefreshView,
    SessionsView,
)

router = DefaultRouter()
router.register(r"personnel", PersonnelViewSet, basename="personnel")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/password/", PasswordChangeView.as_view(), name="auth-password"),
    path("auth/sessions/", SessionsView.as_view(), name="auth-sessions"),
    path("auth/logout-others/", LogoutOthersView.as_view(), name="auth-logout-others"),
    path("", include(router.urls)),
]
