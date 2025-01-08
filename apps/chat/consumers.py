import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message
from config import settings
import redis

redis_instance = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
user_channel_map = {}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.chat_rooms = await self.get_user_chat_rooms(self.user)
        redis_instance.set(f"online_user_{self.user.id}", "1")
        for chat_room in self.chat_rooms:
            await self.channel_layer.group_add(
                f"chat_{chat_room.id}",
                self.channel_name
            )
        user_channel_map[self.user.id] = self.channel_name
        await self.accept()
        await self.update_offline_messages()

    async def disconnect(self, close_code):
        for chat_room in self.chat_rooms:
            await self.channel_layer.group_discard(
                f"chat_{chat_room.id}",
                self.channel_name
            )
        if self.user.id in user_channel_map:
            del user_channel_map[self.user.id]
        redis_instance.delete(f"online_user_{self.user.id}")

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        event_type = text_data_json.get("type")
        chat_room_id = text_data_json.get("chat_room_id")

        if event_type == "send_message":
            message_content = text_data_json["message"]
            chat_room = await self.get_chat_room(chat_room_id)
            if chat_room and chat_room in self.chat_rooms:
                message = await self.create_message(self.user, chat_room, message_content)
                # Notify all users in the chat room
                await self.notify_chat_room_users(chat_room, message)

        elif event_type == "mark_seen":
            message_ids = text_data_json.get("message_ids", [])
            if message_ids:
                await self.mark_messages_as_seen(message_ids, self.user)
                for message_id in message_ids:
                    message = await self.get_message(message_id)
                    chatroom_id, sender_id = await self.get_sender_and_chatroom_id(message)
                    sender_channel_name = user_channel_map.get(sender_id)
                    if sender_channel_name:
                        await self.channel_layer.send(
                            sender_channel_name,
                            {
                                "type": "messages_seen",
                                "message_ids": message_id,
                                "chat_room_id": chatroom_id,
                                "seen_by": self.user.username,
                            },
                        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
            "status": event["status"],
        }))

    async def messages_seen(self, event):
        await self.send(text_data=json.dumps({
            "type": "mark_seen",
            "message_ids": event["message_ids"],
            "chat_room_id": event["chat_room_id"],
            "seen_by": event["seen_by"],
        }))

    @database_sync_to_async
    def get_message(self, id):
        try:
            return Message.objects.get(id=id)
        except Message.DoesNotExist:
            return None

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
    def create_message(self, user, chat_room, message_content):
        return Message.objects.create(chatroom=chat_room, sender=user, content=message_content)

    @database_sync_to_async
    def is_user_online(self, user):
        user_online_key = f"online_user_{user.id}"
        return redis_instance.exists(user_online_key) == 1

    @database_sync_to_async
    def mark_messages_as_seen(self, message_ids, user):
        for message_id in message_ids:
            try:
                message = Message.objects.get(id=message_id, chatroom__users=user)
                message.delivered_to.add(user)
                if message.delivered_to.count() == message.chatroom.users.count():
                    message.status = Message.SEEN
                message.save()
            except Message.DoesNotExist:
                continue

    async def update_offline_messages(self):
        messages = await self.fetch_sent_or_delivered_messages(self.user)
        for message in messages:
            if not await self.has_message_been_delivered_to_user(message, self.user):
                await self.mark_message_as_delivered_to_user(message, self.user)
                await self.send_message_to_user(message)

    async def send_message_to_user(self, message):
        await self.send(text_data=json.dumps({
            "message": message.content,
            "timestamp": message.timestamp.isoformat(),
            "chat_room_id": message.chatroom.id,
            "status": message.status,
        }))

    @database_sync_to_async
    def fetch_sent_or_delivered_messages(self, user):
        return list(
            Message.objects.filter(
                chatroom__users=user,
            ).exclude(
                sender=user
            )
        )

    @database_sync_to_async
    def has_message_been_delivered_to_user(self, message, user):
        return message.delivered_to.filter(id=user.id).exists()

    @database_sync_to_async
    def mark_message_as_delivered_to_user(self, message, user):
        message.delivered_to.add(user)
        if message.delivered_to.count() == message.chatroom.users.count():
            message.status = Message.DELIVERED
        message.save()

    @database_sync_to_async
    def get_sender_and_chatroom_id(self, message):
        return message.chatroom.id, message.sender.id

    @database_sync_to_async
    def get_chat_room_users(self, chat_room):
        return list(chat_room.users.all())

    async def notify_chat_room_users(self, chat_room, message):
        chat_room_users = await self.get_chat_room_users(chat_room)
        for user in chat_room_users:
            recipient_is_online = await self.is_user_online(user)
            if not recipient_is_online:
                continue
            recipient_channel = user_channel_map.get(user.id)
            if recipient_channel:
                await self.channel_layer.send(
                    recipient_channel,
                    {
                        "type": "chat_message",
                        "message": message.content,
                        "timestamp": message.timestamp.isoformat(),
                        "chat_room_id": chat_room.id,
                        "status": Message.DELIVERED,
                    },
                )