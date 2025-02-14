from channels.db import database_sync_to_async
from django.contrib.auth.backends import ModelBackend

from apps.users.models import User


class CustomAuthBackend(ModelBackend):
    """
    Custom authentication backend.

    Allows users to log in using their email address.
    """

    @database_sync_to_async
    def authenticate(self, email=None, password=None, **kwargs):
        """
        Overrides the authenticate method to allow users to log in using their email address.
        """
        try:
            user = User.objects.get(email=email)
            return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        """
        Overrides the get_user method to allow users to log in using their email address.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
