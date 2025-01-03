from rest_framework.views import APIView
from .models import Message
from rest_framework import status
from rest_framework.response import Response
from .models import ChatRoom
from apps.users.models import User


class getmessagehistory(APIView):
    def get(self, request):
        room_id = request.query_params.get('room_id')
        messages = Message.objects.filter(chatroom_id=room_id).order_by('-id')
        data = [{'sender': msg.sender.username, 'content': msg.content, 'timestamp': msg.timestamp} for msg in messages]
        return Response({"data": data}, status=status.HTTP_200_OK)


class GetOrCreateChatRoom(APIView):
    """
    API View to get or create a chat room based on multiple user IDs.
    Returns the chat room ID if the room exists or is created.
    """
    def post(self, request):
        # Get the user IDs from the request data
        user_ids = request.data.get('user_ids')

        # Validate the user IDs
        if not user_ids or len(user_ids) < 2:
            return Response({"detail": "At least two user IDs are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure all users exist
        users = []
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                users.append(user)
            except User.DoesNotExist:
                return Response({"detail": f"User with ID {user_id} not found."}, status=status.HTTP_404_NOT_FOUND)

        # Sort users by ID to ensure consistent chat room creation (optional)
        users.sort(key=lambda x: x.id)

        # Generate a unique chat room ID based on sorted user IDs
        chat_room_id = f"chat_{'_'.join([str(user.id) for user in users])}"

        # Get or create the chat room
        chat_room, created = ChatRoom.objects.get_or_create(id=chat_room_id)

        # Add users to the chat room if it's newly created
        if created:
            chat_room.users.add(*users)

        # Return the chat room ID
        return Response({"chat_room_id": chat_room.id}, status=status.HTTP_200_OK)