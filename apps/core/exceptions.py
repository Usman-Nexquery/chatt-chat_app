import re

from rest_framework.exceptions import APIException


class ApplicationError(APIException):
    def __init__(self, message):
        super().__init__(message)

    status_code = 400


class CustomIntegrityError(APIException):
    def __init__(self, args):
        error_message = args[0]
        field = self.extract_field_from_error(error_message)
        value = self.extract_value_from_error(error_message)
        detail = {field: f"{value} already exists"}
        super().__init__(detail)

    status_code = 400

    @staticmethod
    def extract_field_from_error(error_message):
        # Extract the field name from the error message
        match = re.search(r'Key \((\w+)\)=\((.*?)\)', error_message)
        if match:
            return match.group(1)
        return 'non_field_error'

    @staticmethod
    def extract_value_from_error(error_message):
        # Extract the value from the error message
        match = re.search(r'Key \((\w+)\)=\((.*?)\)', error_message)
        if match:
            return match.group(2)
        return 'non_field_error'
