from functools import partial

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.common.utils import user_directory_path
from apps.users.managers import MyUserManager
from config import settings


# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        verbose_name="email address", max_length=255, unique=True, null=False, blank=False
    )
    username = models.CharField(max_length=255, unique=True, null=False, blank=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = MyUserManager()

    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email


class ResetPassword(models.Model):
    token = models.CharField(max_length=255, unique=True, null=False, blank=False)
    is_blacklisted = models.BooleanField(default=False)
    created_or_updated_at = models.DateTimeField(null=False, blank=False)
    expires_at = models.DateTimeField(null=False, blank=False)
    user = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="reset_password",
    )

    def __str__(self):
        return self.token


class Profile(models.Model):
    class RoleChoices(models.TextChoices):
        BUYER = ("buyer", "buyer")
        SELLER = ("seller", "seller")

    user_directory_profile_path = partial(user_directory_path, folder_name="profile")
    image = models.ImageField(upload_to=user_directory_profile_path, null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    user = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="profile",
    )
    role = models.CharField(
        max_length=50,
        choices=RoleChoices.choices,
        default=RoleChoices.BUYER,
        null=True,
        blank=True,
    )

    def __str__(self):
        return str(self.role)
