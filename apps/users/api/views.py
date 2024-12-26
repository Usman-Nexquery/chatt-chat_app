from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated

from apps.common.utils import get_unique_identifier_stamp
from apps.common.validators import PasswordRegexValidator
from apps.common.views import BaseApiView
from apps.core.authentication import CustomAuthBackend
from apps.users.models import Profile
from apps.users.selectors import get_reset_password, get_tokens_for_user, get_user
from apps.users.services import (
    user_blacklist_refresh_token,
    user_check_password,
    user_create,
    user_profile_create,
    user_reset_password_create_or_update,
    user_reset_password_validation,
    user_update_profile_role,
)
from apps.users.utils import get_email_content_for_forgot_password
from config import settings


class UserCreateApi(BaseApiView):
    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True, allow_blank=False, allow_null=False)
        password = serializers.CharField(
            max_length=255,
            required=True,
            allow_blank=False,
            allow_null=False,
            validators=[PasswordRegexValidator()],
        )
        username = serializers.CharField(required=True,allow_null=False, allow_blank=False)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = user_create(**serializer.validated_data)
            user_profile_create(user=user)
        return self.send_response(
            success=True,
            code="201",
            description="User created successfully",
            status_code=status.HTTP_201_CREATED,
        )


class UserLoginApi(BaseApiView):
    custom_auth_backend = CustomAuthBackend

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True, allow_blank=False, allow_null=False)
        password = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user(email=serializer.validated_data.get("email"))
        user_check_password(user=user, password=serializer.validated_data.get("password"))
        self.custom_auth_backend().authenticate(**serializer.validated_data)
        tokens = get_tokens_for_user(user=user)
        return self.send_response(
            success=True,
            code="200",
            description=tokens,
            status_code=status.HTTP_200_OK,
        )


class UserLogoutApi(BaseApiView):
    class InputSerializer(serializers.Serializer):
        refresh = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_blacklist_refresh_token(refresh=serializer.validated_data.get("refresh"))
        return self.send_response(
            success=True,
            code="201",
            description="Token blacklisted successfully",
            status_code=status.HTTP_201_CREATED,
        )


class UserForgotPasswordApi(BaseApiView):
    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True, allow_blank=False, allow_null=False)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user(email=serializer.validated_data.get("email"))
        unique_identifier = get_unique_identifier_stamp()
        user_reset_password_create_or_update(unique_identifier=unique_identifier, user=user)
        reset_password_link = f"{settings.BASE_FRONTEND_URL}/reset-password/{unique_identifier}/"
        subject, message = get_email_content_for_forgot_password(
            user=user, reset_password_link=reset_password_link
        )
        send_email(to=user.email, subject=subject, message=message)
        return self.send_response(
            success=True,
            code="201",
            description="Reset password link sent successfully, Please check your email",
            status_code=status.HTTP_201_CREATED,
        )


class UserResetPasswordValidateApi(BaseApiView):
    def get(self, request, token: str):
        reset_password = get_reset_password(token=token)
        user_reset_password_validation(reset_password=reset_password)
        return self.send_response(
            success=True,
            code="200",
            description="Link validated successfully",
            status_code=status.HTTP_200_OK,
        )


class UserResetPasswordApi(BaseApiView):
    class InputSerializer(serializers.Serializer):
        password = serializers.CharField(
            required=True,
            allow_blank=False,
            allow_null=False,
            validators=[PasswordRegexValidator()],
        )

    def post(self, request, token: str):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_password = get_reset_password(token=token)
        user_reset_password_validation(reset_password=reset_password)
        reset_password.user.set_password(serializer.validated_data.get("password"))
        reset_password.is_blacklisted = True
        with transaction.atomic():
            reset_password.save()
            reset_password.user.save()
        return self.send_response(
            success=True,
            code="200",
            description="Password reset successfully, Please login with new password",
            status_code=status.HTTP_200_OK,
        )


class UserProfileApi(BaseApiView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Profile
            fields = "__all__"

    def get(self, request):
        user = request.user
        serializer = self.OutputSerializer(user.profile)
        return self.send_response(
            success=True,
            code="200",
            message="Profile retrieved successfully",
            description=serializer.data,
            status_code=status.HTTP_200_OK,
        )


class UserRoleUpdateApi(BaseApiView):

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField(required=True, allow_blank=False, allow_null=False)
        role = serializers.ChoiceField(choices=Profile.RoleChoices.choices, required=True)

    def put(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user(email=serializer.validated_data.get("email"))
        user_update_profile_role(user=user, role=serializer.validated_data.get("role"))
        return self.send_response(
            success=True,
            code="202",
            description="Role updated successfully",
            status_code=status.HTTP_202_ACCEPTED,
        )
