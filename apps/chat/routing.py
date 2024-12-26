from django.urls import re_path
from apps.chat import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/', consumers.ChatConsumer.as_asgi()),  # Static path for all chat connections
]
