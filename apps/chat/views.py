from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Message

@api_view(['GET'])
def get_message_history(request, room_id):
    messages = Message.objects.filter(chatroom_id=room_id)
    data = [{'sender': msg.sender.username, 'content': msg.content, 'timestamp': msg.timestamp} for msg in messages]
    return Response(data)