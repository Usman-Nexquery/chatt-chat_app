import random
import string
import time
import uuid

from config.settings import BASE_BACKEND_URL


def user_directory_path(instance, filename, folder_name=None):
    # file will be uploaded to MEDIA_ROOT/user_<id>/type/<filename>
    return "user_{0}/{1}/{2}".format(instance.user.id, folder_name, filename)


def get_unique_identifier_stamp() -> str:
    token = uuid.uuid4()
    timestamp = str(int(time.time()))
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{token}-{timestamp}-{random_chars}"


def remove_extra_fields_from_validated_data(request_data: dict, serializer_data: dict) -> dict:
    validated_data = {key: value for key, value in serializer_data.items() if key in request_data}
    return validated_data


def get_image_url_if_exists(image_field) -> str:
    # Check if the image exists, return URL if it does, otherwise return an empty string
    return BASE_BACKEND_URL + image_field.url if image_field else ""
