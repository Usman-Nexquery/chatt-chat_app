from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import ApplicationError
from apps.users.models import Profile, ResetPassword, User


def user_create(*,username:str, email: str, password: str) -> User:
    user = User(email=email,username= username)
    user.set_password(password)
    user.save()
    return user


def user_profile_create(*, user: User):
    Profile.objects.create(user=user)


def user_check_password(*, user: User, password: str):
    if not user.check_password(password):
        raise ValidationError({"password": "Incorrect password for this account"})


def user_blacklist_refresh_token(*, refresh: RefreshToken):
    try:
        token = RefreshToken(refresh)
        token.blacklist()
    except TokenError:
        raise ApplicationError("Invalid refresh token provided")


def user_reset_password_create_or_update(*, unique_identifier: str, user: User):
    defaults = {
        "token": unique_identifier,
        "created_or_updated_at": timezone.now(),
        "expires_at": timezone.now() + timedelta(minutes=30),
        "user": user,
        "is_blacklisted": False,
    }
    ResetPassword.objects.update_or_create(user=user, defaults=defaults)


def user_reset_password_validation(*, reset_password: ResetPassword):
    if reset_password.expires_at < timezone.now():
        raise ApplicationError(
            "The provided link has expired, Please request a new password reset email"
        )
    if reset_password.is_blacklisted:
        raise ApplicationError(
            "Link already used for reset password, Please request a new password reset email"
        )


def user_update_profile_role(*, user: User, role: str):
    user.profile.role = role
    user.profile.save()
