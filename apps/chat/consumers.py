import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatRoom, Message
from channels.db import database_sync_to_async
import jwt  # Assuming you're using PyJWT for decoding tokens
from django.conf import settings  # Ensure you're using Django settings for the secret key

from ..users.models import User


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the chat_room_id from URL route
        self.chat_room_id = self.scope["url_route"]["kwargs"]["chat_room_id"]
        self.chat_group_name = f"chat_{self.chat_room_id}"

        # Retrieve or create the chat room (async-safe query)
        self.chat_room = await self.get_chat_room(self.chat_room_id)

        if not self.chat_room:
            # Close connection if chat room does not exist
            await self.close()
            return

        # Extract the JWT token from the Authorization header
        headers = dict(self.scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        token = auth_header.split(" ")[-1] if " " in auth_header else auth_header

        # Authenticate the user using the JWT token
        user = await self.authenticate_user_from_token(token)
        print("my email is", user)
        print(user.is_authenticated)

        if user and user.is_authenticated:
            # Add the user to the chat room if not already part of the room
            await self.add_user_to_chat_room(user)

            # Add the authenticated user to the scope so we can use it in other methods
            self.scope['user'] = user

            # Join the chat group
            await self.channel_layer.group_add(
                self.chat_group_name,
                self.channel_name,
            )

            # Accept the WebSocket connection
            await self.accept()
        else:
            # If authentication fails, close the connection
            await self.close()

    async def disconnect(self, close_code):
        # Retrieve the user from the WebSocket scope
        user = self.scope.get('user')

        if user and user.is_authenticated:
            # Remove the user from the chat room and leave the chat group
            await self.remove_user_from_chat_room(user)

            await self.channel_layer.group_discard(
                self.chat_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_content = text_data_json["message"]

        # Retrieve the user from the WebSocket scope
        user = self.scope.get('user')

        # Create a new message in the database with the timestamp (async-safe)
        message = await self.create_message(user, message_content)

        # Broadcast the message to the chat group, including the timestamp
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                "type": "chat_message",
                "message": message.content,
                "timestamp": message.timestamp.isoformat()  # Include timestamp in ISO format
            },
        )

    async def chat_message(self, event):
        message = event["message"]
        timestamp = event["timestamp"]

        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            "message": message,
            "timestamp": timestamp
        }))

    # Async-safe database methods

    @database_sync_to_async
    def get_chat_room(self, chat_room_id):
        try:
            return ChatRoom.objects.get(id=chat_room_id)
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def add_user_to_chat_room(self, user):
        self.chat_room.users.add(user)

    @database_sync_to_async
    def remove_user_from_chat_room(self, user):
        self.chat_room.users.remove(user)

    @database_sync_to_async
    def create_message(self, user, message_content):
        # Ensure that 'user' is a fully loaded User instance
        try:
            user_instance = User.objects.get(id=user.id)
        except User.DoesNotExist:
            print("user does not exist")  # Fetch the actual User instance
        return Message.objects.create(
            chatroom=self.chat_room,
            sender=user_instance,  # Use the fully loaded User instance
            content=message_content
        )

    @database_sync_to_async
    def authenticate_user_from_token(self, token):
        try:
            # Decode the JWT token to extract user information
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")

            # Retrieve the user based on the user_id from the payload
            if user_id:
                user = User.objects.get(id=user_id)
                return user  # Ensure it's a proper User object
            else:
                return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            print(f"Token error: {e}")
            return None
