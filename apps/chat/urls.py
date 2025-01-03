from django.urls import path

from .views import getmessagehistory, GetOrCreateChatRoom

urlpatterns = [
    path('history/', getmessagehistory.as_view(), name='history'),
    path('room/', GetOrCreateChatRoom.as_view(), name='get_or_create_chat_room'),
]
