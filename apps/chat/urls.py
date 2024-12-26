from django.contrib import admin
from django.urls import path,include

from apps.chat.views import get_message_history

urlpatterns = [
    path('history/', get_message_history(), name='history'),
]