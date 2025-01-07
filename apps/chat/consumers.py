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

        # Update all 'sent' messages to 'delivered'
        await self.update_sent_messages_to_delivered(self.user)

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
        event_type = text_data_json.get("type")  # Determine the type of event
        chat_room_id = text_data_json.get("chat_room_id")

        if event_type == "send_message":
            message_content = text_data_json["message"]

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

        elif event_type == "mark_seen":
            # Handle marking messages as seen
            message_ids = text_data_json.get("message_ids", [])

            # Update the status of the specified messages to 'seen'
            if message_ids:
                await self.mark_messages_as_seen(message_ids, self.user)

                # Notify other participants in the chat room that messages were seen
                await self.channel_layer.group_send(
                    f"chat_{chat_room_id}",
                    {
                        "type": "messages_seen",
                        "message_ids": message_ids,
                        "chat_room_id": chat_room_id,
                        "seen_by": self.user.username,
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

    async def messages_seen(self, event):
        # Notify WebSocket clients that messages were marked as seen
        await self.send(text_data=json.dumps({
            "type": "mark_seen",
            "message_ids": event["message_ids"],
            "chat_room_id": event["chat_room_id"],
            "seen_by": event["seen_by"],
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

    @database_sync_to_async
    def mark_messages_as_seen(self, message_ids, user):
        """
        Mark messages as 'seen' for the given user.
        """
        Message.objects.filter(id__in=message_ids, chatroom__users=user).update(status=Message.SEEN)

    # Refactored Methods
    @database_sync_to_async
    def fetch_sent_messages(self, user):
        """
        Fetch all sent messages for the user that need to be updated to 'delivered'.
        """
        return list(
            Message.objects.filter(
                chatroom__users=user,  # The user is in the chat room
                status=Message.SENT    # Only SENT messages
            ).exclude(
                sender=user             # Exclude messages where the sender is the user
            )
        )

    async def update_and_notify_messages(self, messages):
        """
        Update the status of messages to 'delivered' and notify the sender.
        """
        for message in messages:
            # Update message status
            await self.update_message_status(message, Message.DELIVERED)

            # Notify the sender
            await self.send_delivered_notification(message)

    async def update_sent_messages_to_delivered(self, user):
        """
        Fetch all sent messages for the user and update their status to 'delivered'.
        """
        # Fetch sent messages for the user
        messages = await self.fetch_sent_messages(user)

        # Update the messages and send notifications
        await self.update_and_notify_messages(messages)

    @database_sync_to_async
    def get_chat_room_id(self, message):
        return message.chatroom.id,message.sender.username

    async def send_delivered_notification(self, message):
        """
        Send a notification to the sender that their message has been delivered.
        """
        chat_room_id,sender = await self.get_chat_room_id(message)

        await self.channel_layer.group_send(
            f"chat_{chat_room_id}",  # The group of the chat room
            {
                "type": "message_delivered_notification",  # Custom event type
                "message_id": message.id,
                "chat_room_id": chat_room_id,
                "status": message.status,
                "sender": sender,
                "timestamp": message.timestamp.isoformat(),
            },
        )
    async def message_delivered_notification(self, event):
        """
        Send the delivered notification to the sender.
        """
        await self.send(text_data=json.dumps({
            "type": "message_delivered",
            "message_id": event["message_id"],
            "status": event["status"],
            "sender": event["sender"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
        }))
