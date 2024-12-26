from logging import exception

from django.http import Http404
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import ResetPassword, User


def get_user(*, email: str) -> User:
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        raise Http404("No user with this email exists")


def get_tokens_for_user(*, user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def get_reset_password(*, token: str) -> ResetPassword:
    try:
        return ResetPassword.objects.get(token=token)
    except ResetPassword.DoesNotExist:
        raise Http404("The provided link is broken")

def get_user_from_id(user_id : int) -> User:
    try:
        return User.objects.get(id = user_id)
    except Exception as err:
        print("error is : ",str(err))