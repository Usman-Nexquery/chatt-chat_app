import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            # Add the user to the "online_users" group
            await self.channel_layer.group_add("online_users", self.channel_name)

            # Get chat rooms the user is part of
            self.chat_rooms = await self.get_user_chat_rooms(self.user)

            # Add the user to groups for all chat rooms
            for chat_room in self.chat_rooms:
                await self.channel_layer.group_add(f"chat_{chat_room.id}", self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            # Remove the user from the "online_users" group
            await self.channel_layer.group_discard("online_users", self.channel_name)

            # Remove the user from all chat room groups
            for chat_room in self.chat_rooms:
                await self.channel_layer.group_discard(f"chat_{chat_room.id}", self.channel_name)

    async def receive(self, text_data):
        """
        Handle messages from the WebSocket.
        """
        text_data_json = json.loads(text_data)
        event_type = text_data_json.get("type")

        if event_type == "send_message":
            await self.handle_send_message(text_data_json)
        elif event_type == "update_status":
            await self.handle_update_status(text_data_json)

    async def handle_send_message(self, data):
        """
        Handle sending a message to a chat room.
        """
        message_content = data["message"]
        chat_room_id = data["chat_room_id"]

        # Ensure the user is part of the chat room they are sending a message to
        chat_room = await self.get_chat_room(chat_room_id)
        if chat_room and chat_room in self.chat_rooms:
            # Get the recipient of the message
            recipient = await self.get_recipient(chat_room, self.user)
            recipient_is_online = await self.is_recipient_online(recipient)

            # Set the status based on recipient's online status
            status = Message.DELIVERED if recipient_is_online else Message.SENT

            # Create the message in the database
            message = await self.create_message(self.user, chat_room, message_content, status)

            # Broadcast the message to the chat group
            await self.channel_layer.group_send(
                f"chat_{chat_room.id}",
                {
                    "type": "chat_message",
                    "message": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "chat_room_id": chat_room.id,
                    "status": message.status,
                    "sender": self.user.username,
                    "message_id": message.id,
                },
            )

    async def handle_update_status(self, data):
        """
        Handle updating the status of a message.
        """
        message_id = data["message_id"]
        new_status = data["status"]

        # Update the status in the database
        await self.update_message_status(message_id, new_status)

        # Optionally, broadcast the status update to the chat group
        message = await self.get_message(message_id)
        if message:
            await self.channel_layer.group_send(
                f"chat_{message.chatroom.id}",
                {
                    "type": "status_update",
                    "message_id": message.id,
                    "status": new_status,
                    "chat_room_id": message.chatroom.id,
                },
            )

    async def chat_message(self, event):
        """
        Send the chat message to the WebSocket.
        """
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
            "status": event["status"],
            "sender": event["sender"],
            "message_id": event["message_id"],
        }))

    async def status_update(self, event):
        """
        Send the status update to the WebSocket.
        """
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "message_id": event["message_id"],
            "status": event["status"],
            "chat_room_id": event["chat_room_id"],
        }))

    # Async-safe database methods
    @database_sync_to_async
    def get_user_chat_rooms(self, user):
        return list(user.chatrooms.all())

    @database_sync_to_async
    def get_chat_room(self, chat_room_id):
        try:
            return ChatRoom.objects.get(id=chat_room_id)
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def create_message(self, user, chat_room, message_content, status):
        return Message.objects.create(chatroom=chat_room, sender=user, content=message_content, status=status)

    @database_sync_to_async
    def update_message_status(self, message_id, status):
        try:
            message = Message.objects.get(id=message_id)
            message.status = status
            message.save()
        except Message.DoesNotExist:
            pass

    @database_sync_to_async
    def get_message(self, message_id):
        try:
            return Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def get_recipient(self, chat_room, sender):
        return chat_room.users.exclude(id=sender.id).first()

    @database_sync_to_async
    def is_recipient_online(self, recipient):
        if recipient:
            online_users = self.channel_layer.groups.get("online_users", set())
            return self.channel_name in online_users
        return False