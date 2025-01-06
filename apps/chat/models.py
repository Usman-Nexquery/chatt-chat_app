from django.db import models
from apps.users.models import User


class ChatRoom(models.Model):
    id = models.CharField(max_length=255, primary_key=True)  # Dynamically generated ID
    name = models.CharField(max_length=255, blank=True, null=True)  # Optional room name
    users = models.ManyToManyField(User, related_name="chatrooms")

    def __str__(self):
        return self.name or self.id


class Message(models.Model):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

    STATUS_CHOICES = [
        (SENT, "Sent"),
        (DELIVERED, "Delivered"),
        (READ, "Read"),
    ]

    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SENT)

    def __str__(self):
        return f"{self.sender} -> {self.chatroom.id}: {self.content[:20]}"