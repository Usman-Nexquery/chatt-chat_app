from django.db import models
from apps.users.models import User

class ChatRoom(models.Model):
    id = models.CharField(max_length=255, primary_key=True)  # New id logic based on user IDs
    name = models.CharField(max_length=255, blank=True)  # Optional name field
    users = models.ManyToManyField(User, related_name='chatrooms')

    def __str__(self):
        return self.name or f"ChatRoom-{self.id}"

class Message(models.Model):
    chatroom = models.ForeignKey(ChatRoom, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)  # Automatically set on creation

    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"
