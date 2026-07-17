"""Authentication and Authorization Utilities.

Provides password hashing/verification, password strength validation, JWT token
generation (access and refresh), token verification, and a Flask route decorator
to enforce authentication using access tokens.
"""

import functools
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from flask import g, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

from app.config.settings import Config
from app.utils.logger import get_logger

logger = get_logger("auth")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Werkzeug's secure hashing scheme.

    Args:
        password: The plaintext password.

    Returns:
        The hashed password string.
    """
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Args:
        password: The candidate plaintext password.
        password_hash: The stored password hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return check_password_hash(password_hash, password)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate that a password meets minimum strength requirements.

    Requirements:
    - Minimum 8 characters.
    - At least one uppercase letter.
    - At least one lowercase letter.
    - At least one digit.

    Args:
        password: The password string to validate.

    Returns:
        A tuple of (is_strong, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(char.islower() for char in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit."
    return True, "Password meets strength requirements."


def generate_access_token(user_id: str) -> str:
    """Generate a signed JWT access token for a user.

    Args:
        user_id: The unique identifier of the user.

    Returns:
        A signed JWT access token.

    Raises:
        RuntimeError: If JWT_SECRET_KEY is not configured.
    """
    if not Config.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured. Please set it in your .env file.")

    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=Config.JWT_ACCESS_EXPIRY_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expiry,
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def generate_refresh_token(user_id: str) -> str:
    """Generate a signed JWT refresh token for a user.

    Args:
        user_id: The unique identifier of the user.

    Returns:
        A signed JWT refresh token.

    Raises:
        RuntimeError: If JWT_SECRET_KEY is not configured.
    """
    if not Config.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured. Please set it in your .env file.")

    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=Config.JWT_REFRESH_EXPIRY_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expiry,
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def verify_token(token: str, expected_type: str) -> Optional[dict]:
    """Decode and validate a JWT, ensuring signature, expiry, and token type match.

    Args:
        token: The raw JWT string.
        expected_type: The expected token type (e.g., "access" or "refresh").

    Returns:
        The decoded payload dict if the token is valid, or None if validation fails.
    """
    if not Config.JWT_SECRET_KEY:
        logger.error("JWT_SECRET_KEY is not configured.")
        return None

    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            logger.warning(
                f"Token validation failed: type claim '{payload.get('type')}' "
                f"does not match expected '{expected_type}'."
            )
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning(f"Token validation failed: token of type '{expected_type}' has expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Token validation failed: {exc}")
        return None


def require_auth(f):
    """Decorator to protect Flask endpoints using Bearer access tokens.

    Extracts token from `Authorization: Bearer <token>`, verifies it as a valid,
    non-expired ACCESS token, checks if user exists in database and is active,
    and sets `flask.g.current_user`.

    Returns:
        401 if authentication fails, 403 if the user account is inactive.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header: str = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Authentication failed: Missing or malformed Authorization header.")
            return jsonify({"success": False, "error": "Missing or invalid authorization token."}), 401

        token = auth_header.split(" ", 1)[1].strip()
        payload = verify_token(token, "access")
        if not payload:
            return jsonify({"success": False, "error": "Missing or invalid authorization token."}), 401

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Authentication failed: Missing subject claim in access token.")
            return jsonify({"success": False, "error": "Missing or invalid authorization token."}), 401

        from app.models.user import User
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.warning(f"Authentication failed: User with ID {user_id} not found in database.")
            return jsonify({"success": False, "error": "User not found."}), 401

        if not user.is_active:
            logger.warning(f"Authentication failed: User account with ID {user_id} is inactive.")
            return jsonify({"success": False, "error": "User account is disabled."}), 403

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """Decorator to protect Flask endpoints using Bearer access tokens, and check for admin role.

    Returns:
        403 if the user is not an admin.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, "current_user") or getattr(g.current_user, "role", "user") != "admin":
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return require_auth(decorated)
