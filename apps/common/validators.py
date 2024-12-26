import re

from rest_framework import serializers


class WhiteSpaceValidator:
    """
    This method is automatically called by drf with the value of field whenever an object of
    this class is instantiated.
    """

    def __call__(self, value):
        if re.search(r'\s+', value):
            message = "Whitespace are not allowed."
            raise serializers.ValidationError(message)


class PasswordRegexValidator:
    """
    This method is automatically called by drf with the value of field whenever an object of
    this class is instantiated.
    """

    def __call__(self, value):
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*?&]{8,20}$'
        if not re.fullmatch(pattern, value):
            message = "Must be 8-20 characters long, include letters and numbers"
            raise serializers.ValidationError(message)
