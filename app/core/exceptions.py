"""Custom exceptions for the Jogy App backend."""


class JogyException(Exception):
    """Base exception for Jogy App."""
    
    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred"
    
    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)


# ============================================================
# Authentication Exceptions
# ============================================================

class InvalidCredentialsError(JogyException):
    """Raised when login credentials are invalid."""
    
    code = "INVALID_CREDENTIALS"
    message = "Invalid username or password"


class InvalidTokenError(JogyException):
    """Raised when a token is invalid or expired."""
    
    code = "INVALID_TOKEN"
    message = "Invalid or expired token"


class UserDisabledError(JogyException):
    """Raised when user account is disabled."""
    
    code = "USER_DISABLED"
    message = "User account is disabled"


# ============================================================
# Registration Exceptions
# ============================================================

class UsernameTakenError(JogyException):
    """Raised when username is already taken."""
    
    code = "USERNAME_TAKEN"
    message = "Username already exists"


class EmailTakenError(JogyException):
    """Raised when email is already taken."""
    
    code = "EMAIL_TAKEN"
    message = "Email already exists"
