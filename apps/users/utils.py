from apps.users.models import User


def get_email_content_for_forgot_password(
    *, user: User, reset_password_link: str
) -> tuple[str, str]:
    subject = "Subject : Reset Your Password"
    message = (
        f"Dear {user.email},\n\n"
        f"We have received a request to reset your password.\n"
        f"To reset your password, please click on the following link:\n{reset_password_link}\n\n"
        f"If you did not request to reset your password, "
        f"Please ignore this email and your account will remain unchanged.\n"
        f"Please note that the link will expire in 30 Minutes. If the link expires, "
        f"you will need to request another password reset.\n\n"
        f"Thank you,\n\nOperations Team."
    )
    return subject, message
