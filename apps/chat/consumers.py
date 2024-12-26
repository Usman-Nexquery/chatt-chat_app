import json
from channels.generic.websocket import AsyncWebsocketConsumer
from apps.users.models import User  # Import your custom User model
from apps.chat.models import Message, ChatRoom
from apps.core.authentication import CustomAuthBackend
from channels.db import database_sync_to_async
import jwt  # Assuming you're using PyJWT for decoding tokens
from apps.users.selectors import get_user_from_id  # Import the selector function
from config import settings


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get the `authorization` header
        headers = dict(self.scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        # Split by whitespace and extract the token
        if " " in auth_header:
            token = auth_header.split(" ")[-1]  # Extract the last part after "Bearer" or any prefix
        else:
            token = auth_header  # No prefix, assume it's just the token

        print(f"Extracted Token: {token}")

        # Check if token exists
        if not token:
            await self.close()
            return

        # Decode the JWT token to get the email
        user_email = await self.decode_token_and_get_email(token)
        if not user_email:
            await self.close()
            return

        # Now, authenticate the user using the email
        user = await self.get_user_from_email(user_email)
        if not user:
            await self.close()
            return

        # Attach the authenticated user to the scope
        self.scope['user'] = user

        # Proceed with WebSocket connection
        self.room_name = None
        self.room_group_name = None
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json.get("message", None)
        room_id = text_data_json.get("room_id", None)

        if room_id is not None:
            self.room_group_name = f"chat_{room_id}"
            chat_room = await self.get_chat_room(room_id)
            if chat_room:
                await self.save_message(chat_room, message)
                await self.send_chat_message_to_room(message)
        else:
            await self.send({
                'type': 'websocket.close'
            })

    async def send_chat_message_to_room(self, message):
        if self.room_group_name:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                }
            )

    async def chat_message(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({
            "message": message
        }))

    async def decode_token_and_get_email(self, token):
        """
        Decodes the JWT token and retrieves the email from it.
        This method assumes you are using JWT with a payload that includes the email.
        """
        try:
            # Decode the token using your secret key (configured in settings)
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            # Now wrap the get_user_from_id in database_sync_to_async
            user = await self.get_user_from_id(payload.get("user_id"))

            if not user:
                return None

            user_email = user.email
            print(f"user email : {user_email}")
            return user_email
        except jwt.ExpiredSignatureError:
            print("Token expired.")
            return None
        except jwt.InvalidTokenError:
            print("Invalid token.")
            return None

    @database_sync_to_async
    def get_user_from_id(self, user_id):
        """
        This function is now wrapped with `database_sync_to_async`
        to allow it to run in an async context.
        """
        try:
            user = User.objects.get(id=user_id)
            return user
        except User.DoesNotExist:
            return None

    async def get_user_from_email(self, email):
        """
        Authenticates the user based on the extracted email.
        This function calls the custom authentication backend to authenticate the user.
        """
        try:
            # Use your custom authentication backend to get the user
            custom_auth_backend = CustomAuthBackend()
            user = custom_auth_backend.authenticate(email=email)
            return user
        except Exception as e:
            print(f"Error in user authentication: {e}")
            return None

    async def get_chat_room(self, room_id):
        try:
            chat_room = await database_sync_to_async(ChatRoom.objects.get)(id=room_id)
            return chat_room
        except ChatRoom.DoesNotExist:
            return None

    async def save_message(self, chat_room, message_text):
        try:
            # Save message in the database
            message = await database_sync_to_async(Message.objects.create)(
                chat_room=chat_room,
                user=self.scope['user'],
                text=message_text,
            )
            return message
        except Exception as e:
            print(f"Error saving message: {e}")
            return None
