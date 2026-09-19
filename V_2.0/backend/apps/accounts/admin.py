from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Plain ModelAdmin rather than django.contrib.auth.admin.UserAdmin,
    since that base class's forms (UserCreationForm/UserChangeForm) assume
    the default `username` field — this model uses `national_code` as
    USERNAME_FIELD instead."""

    model = User
    ordering = ["national_code"]
    list_display = ["national_code", "full_name", "access_roll", "access_level", "title", "is_active", "is_staff"]
    list_filter = ["access_roll", "access_level", "is_active", "is_staff"]
    search_fields = ["national_code", "full_name", "mobile_phone"]
    # "password" is readonly here (shows the hash) rather than editable
    # plaintext — use the API (which calls set_password) or `changepassword`
    # management command to actually change a password.
    readonly_fields = ["date_joined", "last_login", "password"]
    filter_horizontal = ["groups", "user_permissions"]

    fieldsets = (
        (None, {"fields": ("national_code", "password")}),
        ("Personal info", {"fields": ("full_name", "mobile_phone")}),
        ("RBAC", {"fields": ("access_roll", "access_level")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    @admin.display(description="Title")
    def title(self, obj):
        return obj.title
