from django.contrib import admin

from apps.chat.models import Message, ChatRoom

admin.site.register(ChatRoom)
admin.site.register(Message)
