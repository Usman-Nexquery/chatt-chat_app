from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.api.views import (
    UserCreateApi,
    UserForgotPasswordApi,
    UserLoginApi,
    UserLogoutApi,
    UserProfileApi,
    UserResetPasswordApi,
    UserResetPasswordValidateApi,
    UserRoleUpdateApi,
)

urlpatterns = [
    path("register/", UserCreateApi.as_view(), name="user-register"),
    path("login/", UserLoginApi.as_view(), name="user-login"),
    path("logout/", UserLogoutApi.as_view(), name="user-logout"),
    path('refresh/', TokenRefreshView.as_view(), name='user-token-refresh'),
    path("forgot-password/", UserForgotPasswordApi.as_view(), name="user-forgot-password"),
    path(
        "validate/reset-password/<str:token>/",
        UserResetPasswordValidateApi.as_view(),
        name="user-validate-reset_password",
    ),
    path("reset-password/<str:token>/", UserResetPasswordApi.as_view(), name="user-reset-password"),
    # TODO: added profile url for testing to be refactored later
    path("profile/", UserProfileApi.as_view(), name="user-profile"),
    path("update-role/", UserRoleUpdateApi.as_view(), name="user-role-update"),
]
