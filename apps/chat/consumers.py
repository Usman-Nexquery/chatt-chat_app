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
                recipient = await self.get_chat_room_recipient(chat_room, self.user)
                message = await self.create_message(self.user, chat_room, message_content)
                recipient_is_online = await self.is_user_online(recipient)
                new_status = Message.DELIVERED if recipient_is_online else Message.SENT
                await self.update_message_status(message, new_status)
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
            message_ids = text_data_json.get("message_ids", [])
            if message_ids:
                # Mark the messages as seen
                await self.mark_messages_as_seen(message_ids, self.user)
                # Find the sender of the message and send the acknowledgment to their channel
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
    def get_chat_room_recipient(self, chat_room, sender):
        users = chat_room.users.exclude(id=sender.id)
        return users.first() if users.exists() else None

    @database_sync_to_async
    def create_message(self, user, chat_room, message_content):
        return Message.objects.create(chatroom=chat_room, sender=user, content=message_content)

    @database_sync_to_async
    def is_user_online(self, user):
        user_online_key = f"online_user_{user.id}"
        return redis_instance.exists(user_online_key) == 1

    @database_sync_to_async
    def mark_messages_as_seen(self, message_ids, user):
        Message.objects.filter(id__in=message_ids, chatroom__users=user).update(status=Message.SEEN)

    async def update_offline_messages(self):
        messages = await self.fetch_sent_messages(self.user)
        for message in messages:
            updated_message = await self.update_message_status(message, Message.DELIVERED)
            await self.send_delivered_notification(updated_message)
            await self.send_message_to_user(updated_message)

    async def send_message_to_user(self, message):
        await self.send(text_data=json.dumps({
            "message": message.content,
            "timestamp": message.timestamp.isoformat(),
            "chat_room_id": message.chatroom.id,
            "status": message.status,
        }))

    @database_sync_to_async
    def fetch_sent_messages(self, user):
        return list(
            Message.objects.filter(
                chatroom__users=user,
                status=Message.SENT
            ).exclude(
                sender=user
            )
        )

    @database_sync_to_async
    def update_message_status(self, message, status):
        message.status = status
        message.save()
        return message

    @database_sync_to_async
    def get_sender_and_chatroom_id(self, message):
        return message.chatroom.id, message.sender.id

    async def send_delivered_notification(self, message):
        chatroom_id, sender_id = await self.get_sender_and_chatroom_id(message)
        sender_channel_name = user_channel_map.get(message.sender.id)

        if sender_channel_name:
            await self.channel_layer.send(
                sender_channel_name,
                {
                    "type": "message_delivered_notification",
                    "message_id": message.id,
                    "status": message.status,
                    "sender": sender_id,
                    "timestamp": message.timestamp.isoformat(),
                    "chat_room_id": chatroom_id,
                },
            )

    async def message_delivered_notification(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_delivered",
            "message_id": event["message_id"],
            "status": event["status"],
            "sender": event["sender"],
            "timestamp": event["timestamp"],
            "chat_room_id": event["chat_room_id"],
        }))
