from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


# Create your views here.
class BaseApiView(APIView):
    @classmethod
    def send_response(
        cls,
        success=False,
        code="",
        message="",
        description="",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        return Response(
            {"success": success, "code": code, "message": message, "description": description},
            status=status_code,
        )
