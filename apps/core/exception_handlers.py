from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler

from apps.core.exceptions import ApplicationError, CustomIntegrityError


def custom_exception_handler(exc, ctx):
    """
    {
        "success" = bool,
        "code" = str,
        "message = str,
        "description": dict,
    }
    """
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(as_serializer_error(exc))

    if isinstance(exc, Http404):
        exc = exceptions.NotFound(exc)

    if isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, IntegrityError):
        exc = CustomIntegrityError(exc.args)

    if isinstance(exc, ApplicationError):
        exc = ApplicationError(exc)

    response = exception_handler(exc, ctx)

    # If unexpected error occurs (server error, etc.)
    if response is None:
        return response

    if isinstance(exc.detail, (list, dict)):
        response.data = {"detail": response.data}

    # Adding extra information in response
    response.data["success"] = False
    response.data["code"] = str(response.status_code)

    # Adding appropriate error message according to exception
    if isinstance(exc, exceptions.ValidationError):
        response.data["message"] = "Validation error"
    elif isinstance(exc, exceptions.NotFound):
        response.data["message"] = "Not found"
    elif isinstance(exc, CustomIntegrityError):
        response.data["message"] = "Integrity Error"
    elif isinstance(exc, ApplicationError):
        response.data["message"] = "Application Error"
    else:
        response.data["message"] = "Other exception"

    response.data["description"] = response.data["detail"]
    del response.data["detail"]

    return response
