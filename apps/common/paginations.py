from abc import ABC, abstractmethod

from rest_framework import pagination


class CustomLimitOffsetPagination(ABC, pagination.LimitOffsetPagination):
    default_limit = 10
    max_limit = 10

    @abstractmethod
    def get_paginated_response(self, data):
        pass
