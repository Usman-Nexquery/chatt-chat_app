import jwt
from  config.settings import SECRET_KEY
from channels.db import database_sync_to_async
from .models import User


class TokenAuthenticationMiddleware:
    """
    Custom WebSocket middleware to handle token-based authentication
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Extract authorization token from headers
        headers = dict(scope.get("headers"))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        token = auth_header.split(" ")[-1] if " " in auth_header else auth_header

        # Authenticate the user
        user = await self.authenticate_user_from_token(token)

        # Add the user to the scope if authenticated
        if user and user.is_authenticated:
            scope["user"] = user
            return await self.inner(scope, receive, send)
        else:
            # If authentication fails, close the connection
            await send({
                "type": "websocket.close",
                "code": 4000,  # Optional code
            })
            return None

    @database_sync_to_async
    def authenticate_user_from_token(self, token):
        try:
            # Decode the JWT token
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")

            # Retrieve the user
            if user_id:
                return User.objects.get(id=user_id)
            return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None