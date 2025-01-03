import json
from channels.generic.websocket import AsyncWebsocketConsumer
from apps.users.models import User  # Import your custom User model
from apps.chat.models import Message, ChatRoom
from apps.core.authentication import CustomAuthBackend
import jwt  # Assuming you're using PyJWT for decoding tokens
from config import settings
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the `authorization` header
        headers = dict(self.scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        # Extract token from the header
        token = auth_header.split(" ")[-1] if " " in auth_header else auth_header

        # Check if token exists
        if not token:
            await self.close()
            return

        # Decode the JWT token and get the user email
        user_email = await self.decode_token_and_get_email(token)
        if not user_email:
            await self.close()
            return

        # Authenticate the user using the email
        user = await self.get_user_from_email(user_email)
        if not user:
            await self.close()
            return

        # Attach the authenticated user to the scope
        self.scope['user'] = user

        # Get or create the chat room with the users
        user_ids = self.scope['user'].id
        chat_room = await self.get_or_create_chat_room([user_ids])  # you can modify this line to accept multiple users

        if chat_room:
            self.chat_room = chat_room  # Assign chat room to the instance

            # Add user to the group for broadcasting messages
            await self.channel_layer.group_add(
                str(chat_room.id),  # The group name is the chat room id
                self.channel_name
            )

            # Accept the WebSocket connection
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Leave the chat room group
        if hasattr(self, 'chat_room'):
            await self.channel_layer.group_discard(
                str(self.chat_room.id),  # The group name is the chat room id
                self.channel_name
            )

    async def receive(self, text_data):
        # Parse received data
        text_data_json = json.loads(text_data)
        message = text_data_json.get("message", None)
        user_ids = text_data_json.get("user_ids", None)

        if user_ids and message:
            # Ensure the sender is in the list of user IDs
            if self.scope['user'].id not in user_ids:
                user_ids.append(self.scope['user'].id)

            # Get or create the chat room
            chat_room = await self.get_or_create_chat_room(user_ids)
            if chat_room:
                # Save the message
                await self.save_message(chat_room, message)

                # Fetch all messages from the chat room
                messages = await self.get_messages_from_room(chat_room)

                # Broadcast the message to all connected users in the chat room
                await self.channel_layer.group_send(
                    str(chat_room.id),  # The group name is the chat room id
                    {
                        "type": "chat_message",  # Custom message type to handle in `chat_message`
                        "messages": messages
                    }
                )
            else:
                await self.close()
        else:
            await self.close()

    async def chat_message(self, event):
        # Send the message to the WebSocket
        await self.send(text_data=json.dumps({
            "messages": event["messages"]
        }))

    async def decode_token_and_get_email(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user = await self.get_user_from_id(payload.get("user_id"))
            return user.email if user else None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            print(f"Token error: {e}")
            return None

    @database_sync_to_async
    def get_user_from_email(self, email):
        try:
            custom_auth_backend = CustomAuthBackend()
            return custom_auth_backend.authenticate(email=email)
        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    @database_sync_to_async
    def get_user_from_id(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_or_create_chat_room(self, user_ids):
        # Sort user IDs to ensure consistent order
        user_ids = sorted(user_ids)

        # Attempt to find an existing chat room with these users
        try:
            chat_rooms = ChatRoom.objects.filter(users__id__in=user_ids).distinct()
            for chat_room in chat_rooms:
                if chat_room.users.count() == len(user_ids):
                    return chat_room

            # Create a new chat room if none exists
            chat_room = ChatRoom.objects.create(name="Chat Room")
            chat_room.users.add(*user_ids)
            return chat_room
        except Exception as e:
            print(f"Error in get_or_create_chat_room: {e}")
            return None

    @database_sync_to_async
    def get_messages_from_room(self, chat_room):
        # Fetch all messages from the chat room, ordered by timestamp
        messages = Message.objects.filter(chatroom=chat_room).order_by('timestamp')
        return [
            {
                "sender": message.sender.username,
                "content": message.content,
                "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for message in messages
        ]

    @database_sync_to_async
    def save_message(self, chat_room, message_text):
        try:
            return Message.objects.create(
                chatroom=chat_room,
                sender=self.scope['user'],
                content=message_text,
            )
        except Exception as e:
            print(f"Error saving message: {e}")
            return None
