import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message
from config import settings
import redis

# Initialize Redis instance
redis_instance = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get the user from the scope (attached by the authentication middleware)
        self.user = self.scope["user"]

        # Fetch all chat rooms the user is part of
        self.chat_rooms = await self.get_user_chat_rooms(self.user)

        # Mark the user as online in Redis
        redis_instance.set(f"online_user_{self.user.id}", "1")

        # Add user to online group for each chat room
        for chat_room in self.chat_rooms:
            await self.channel_layer.group_add(
                f"chat_{chat_room.id}",  # Unique group for each chat room
                self.channel_name
            )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from all chat room groups
        for chat_room in self.chat_rooms:
            await self.channel_layer.group_discard(
                f"chat_{chat_room.id}",
                self.channel_name
            )

        # Remove user from Redis online tracking
        redis_instance.delete(f"online_user_{self.user.id}")

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_content = text_data_json["message"]
        chat_room_id = text_data_json["chat_room_id"]

        # Fetch the chat room and ensure the user is part of it
        chat_room = await self.get_chat_room(chat_room_id)
        if chat_room and chat_room in self.chat_rooms:
            # Get the recipient (users in the chat room excluding the sender)
            recipient = await self.get_chat_room_recipient(chat_room, self.user)

            # Create a new message in the database
            message = await self.create_message(self.user, chat_room, message_content)

            # Check if the recipient is online using Redis
            recipient_is_online = await self.is_user_online(recipient)

            # Update message status to 'delivered' if recipient is online, otherwise leave it as 'sent'
            new_status = Message.DELIVERED if recipient_is_online else Message.SENT
            await self.update_message_status(message, new_status)

            # Broadcast the message to the chat room group
            await self.channel_layer.group_send(
                f"chat_{chat_room.id}",
                {
                    "type": "chat_message",
                    "message": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "chat_room_id": chat_room.id,
                    "status": new_status,
                },
            )

    async def chat_message(self, event):
        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
            "status": event["status"],
        }))

    # Async-safe database methods
    @database_sync_to_async
    def get_user_chat_rooms(self, user):
        # Get all chat rooms the user is a part of
        return list(user.chatrooms.all())

    @database_sync_to_async
    def get_chat_room(self, chat_room_id):
        try:
            return ChatRoom.objects.get(id=chat_room_id)
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def get_chat_room_recipient(self, chat_room, sender):
        # Get the recipient (users in the chat room excluding the sender)
        users = chat_room.users.exclude(id=sender.id)
        return users.first() if users.exists() else None

    @database_sync_to_async
    def create_message(self, user, chat_room, message_content):
        return Message.objects.create(chatroom=chat_room, sender=user, content=message_content)

    @database_sync_to_async
    def update_message_status(self, message, status):
        message.status = status
        message.save()
        return message

    @database_sync_to_async
    def is_user_online(self, user):
        """
        Check if the given user is online using Redis.
        """
        # Generate the Redis key for the user's online status
        user_online_key = f"online_user_{user.id}"
        return redis_instance.exists(user_online_key) == 1