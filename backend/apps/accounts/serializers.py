from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


def check_password_strength(password: str, user) -> None:
    """Django's validators (length, common, all digits, similar to the name or national code), with
    their Persian messages (LANGUAGE_CODE=fa) under the `password` key."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})


class UserSerializer(serializers.ModelSerializer):
    title = serializers.ReadOnlyField()
    capabilities = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            "id",
            "national_code",
            "full_name",
            "mobile_phone",
            "access_roll",
            "access_level",
            "title",
            "capabilities",
            "is_active",
            "is_staff",
            "is_developer",
            "date_joined",
            "must_change_password",
            "password",
        ]
        # is_staff grants Django admin access and is deliberately not settable
        # through the personnel API — grant it via the admin or a shell. is_developer is set only by
        # the first-run setup bootstrap.
        read_only_fields = [
            "id",
            "title",
            "capabilities",
            "is_staff",
            "is_developer",
            "date_joined",
            "must_change_password",
        ]

    def get_capabilities(self, obj) -> list[str]:
        return sorted(obj.capabilities)

    def validate(self, attrs):
        password = attrs.get("password")
        if password:
            candidate = self.instance or User(
                national_code=attrs.get("national_code", ""), full_name=attrs.get("full_name", "")
            )
            check_password_strength(password, candidate)
        return attrs

    def _set_by_someone_else(self, person) -> bool:
        request = self.context.get("request")
        return request is None or getattr(request.user, "pk", None) != person.pk

    def create(self, validated_data):
        """Registering someone means choosing their first password for them: they must replace it on
        their first sign-in (owner's decision, Phase 20)."""
        password = validated_data.pop("password", None)
        return User.objects.create_user(password=password, must_change_password=bool(password), **validated_data)

    def update(self, instance, validated_data):
        """A password HR sets is a reset: the person must choose a new one and every device they were
        signed in on is signed out. (Setting your own here — the developer editing themselves — is not.)"""
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
            if self._set_by_someone_else(instance):
                instance.must_change_password = True
                instance.revoke_sessions()
        instance.save()
        return instance


class PlacementSerializer(serializers.Serializer):
    """The optional `placement` a personnel registration may carry. `node` stays a bare id —
    accounts must never import `apps.organization` at module level (see the note at
    `views.py` on `PersonnelViewSet.create`), so the view resolves and locks the node itself."""

    node = serializers.IntegerField()
    is_lead = serializers.BooleanField(required=False, default=False)
    position_label = serializers.CharField(required=False, default="", allow_blank=True, max_length=255)


class LoginSerializer(serializers.Serializer):
    national_code = serializers.CharField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": ["رمز عبور فعلی درست نیست."]})
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError({"new_password": ["رمز تازه باید با رمز فعلی فرق داشته باشد."]})
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class TitleSerializer(serializers.Serializer):
    title = serializers.CharField()
