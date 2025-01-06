import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message
from ..users.models import User
import jwt
from django.conf import settings


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Authenticate the user
        headers = dict(self.scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        token = auth_header.split(" ")[-1] if " " in auth_header else auth_header

        self.user = await self.authenticate_user_from_token(token)

        if self.user and self.user.is_authenticated:
            # Add the authenticated user to the scope
            self.scope['user'] = self.user
            # Get chat rooms the user is part of
            self.chat_rooms = await self.get_user_chat_rooms(self.user)
            # Add the user to groups for all chat rooms they are a part of
            for chat_room in self.chat_rooms:
                await self.channel_layer.group_add(
                    f"chat_{chat_room.id}",  # Using chat room ID to create a unique group for each chat room
                    self.channel_name
                )

            # Accept the WebSocket connection
            await self.accept()
        else:
            # Close the connection if authentication fails
            await self.close()

    async def disconnect(self, close_code):
        # Remove the user from all chat room groups
        for chat_room in self.chat_rooms:
            await self.channel_layer.group_discard(
                f"chat_{chat_room.id}",
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_content = text_data_json["message"]
        chat_room_id = text_data_json["chat_room_id"]

        # Ensure the user is part of the chat room they are sending a message to
        chat_room = await self.get_chat_room(chat_room_id)
        if chat_room and chat_room in self.chat_rooms:
            # Create a new message in the database
            message = await self.create_message(self.user, chat_room, message_content)

            # Broadcast the message to the chat group
            await self.channel_layer.group_send(
                f"chat_{chat_room.id}",
                {
                    "type": "chat_message",
                    "message": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "chat_room_id": chat_room.id,
                },
            )

    async def chat_message(self, event):
        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
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
    def create_message(self, user, chat_room, message_content):
        return Message.objects.create(chatroom=chat_room, sender=user, content=message_content)

    @database_sync_to_async
    def authenticate_user_from_token(self, token):
        try:
            # Decode the JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")

            # Retrieve the user
            if user_id:
                return User.objects.get(id=user_id)
            else:
                return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
