from rest_framework import serializers

from .models import User


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
            "password",
        ]
        # is_staff grants Django admin access and is deliberately not settable
        # through the personnel API — grant it via the admin or a shell. is_developer is set only by
        # the first-run setup bootstrap.
        read_only_fields = ["id", "title", "capabilities", "is_staff", "is_developer", "date_joined"]

    def get_capabilities(self, obj) -> list[str]:
        return sorted(obj.capabilities)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    national_code = serializers.CharField()
    password = serializers.CharField(write_only=True)


class TitleSerializer(serializers.Serializer):
    title = serializers.CharField()
