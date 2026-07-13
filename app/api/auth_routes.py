"""Authentication routes blueprint.

Defines signup, login, token refresh, logout, user profile retrieval, and password change
endpoints with rate limiting and secure database storage of refresh token hashes.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Tuple

import jwt
from flask import Blueprint, g, jsonify, request, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config.settings import Config
from app.models import db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.utils.auth import (
    generate_access_token,
    generate_refresh_token,
    hash_password,
    require_auth,
    validate_password_strength,
    verify_password,
    verify_token,
)
from app.utils.logger import get_logger

logger = get_logger("auth_routes")

# Create the auth blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Setup Flask-Limiter for authentication endpoints
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Regex for basic email format validation
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def is_valid_email(email: str) -> bool:
    """Validate email format using a standard regular expression.

    Args:
        email: The candidate email string.

    Returns:
        True if the format is valid, False otherwise.
    """
    return bool(EMAIL_REGEX.match(email))


@auth_bp.route("/signup", methods=["POST"])
def signup() -> Tuple[Response, int]:
    """Register a new user account.

    Validates input fields, username/email uniqueness, email format,
    and password strength. On success, creates the user and logs them in
    by returning access and refresh tokens.

    JSON Body:
        username (str): The chosen username.
        email (str): The user's email address.
        password (str): The plaintext password.

    Returns:
        201: tokens, expiry, and user profile on success.
        400/409: error message on validation failure.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"success": False, "error": "Username, email, and password are required."}), 400

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Invalid email format."}), 400

    is_strong, strength_err = validate_password_strength(password)
    if not is_strong:
        return jsonify({"success": False, "error": strength_err}), 400

    # Check database for uniqueness
    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        if existing_user.username == username:
            return jsonify({"success": False, "error": "Username is already taken."}), 409
        else:
            return jsonify({"success": False, "error": "Email is already registered."}), 409

    try:
        # Create user
        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_verified=True,
        )
        db.session.add(new_user)
        db.session.commit()

        # Auto-login: generate tokens
        access_token = generate_access_token(new_user.id)
        refresh_token = generate_refresh_token(new_user.id)

        # Hash refresh token and save to DB
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        refresh_payload = jwt.decode(refresh_token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

        db_refresh_token = RefreshToken(
            user_id=new_user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        db.session.add(db_refresh_token)
        db.session.commit()

        logger.info(f"User signup successful: {username} ({new_user.id})")

        return jsonify({
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_expires_at": jwt.decode(access_token, Config.JWT_SECRET_KEY, algorithms=["HS256"])["exp"],
            "refresh_expires_at": refresh_payload["exp"],
            "user": {
                "id": str(new_user.id),
                "username": new_user.username,
                "email": new_user.email,
                "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
            }
        }), 201

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to register user: {exc}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred during signup."}), 500


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login() -> Tuple[Response, int]:
    """Authenticate an existing user.

    Validates login credentials, checks if the user is active,
    generates new access and refresh tokens, and saves a hash of the refresh token.

    JSON Body:
        username_or_email (str): The username or email.
        password (str): The plaintext password.

    Returns:
        200: tokens, expiry, and user profile on success.
        401: error message on invalid credentials.
        403: error message if user account is inactive.
    """
    data = request.get_json(silent=True) or {}
    username_or_email = data.get("username_or_email", "").strip()
    password = data.get("password", "")

    if not username_or_email or not password:
        return jsonify({"success": False, "error": "Username/email and password are required."}), 400

    # Look up user by username OR email
    user = User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email)
    ).first()

    # Generic error message to prevent username enumeration
    generic_auth_error = jsonify({"success": False, "error": "Invalid username/email or password."}), 401

    if not user:
        return generic_auth_error

    if not verify_password(password, user.password_hash):
        return generic_auth_error

    if not user.is_active:
        logger.warning(f"Login failed: User account {user.username} is disabled.")
        return jsonify({"success": False, "error": "User account is disabled."}), 403

    try:
        # Generate tokens
        access_token = generate_access_token(user.id)
        refresh_token = generate_refresh_token(user.id)

        # Hash refresh token and save to DB
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        refresh_payload = jwt.decode(refresh_token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

        db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        db.session.add(db_refresh_token)
        db.session.commit()

        logger.info(f"User login successful: {user.username} ({user.id})")

        return jsonify({
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_expires_at": jwt.decode(access_token, Config.JWT_SECRET_KEY, algorithms=["HS256"])["exp"],
            "refresh_expires_at": refresh_payload["exp"],
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to log in user: {exc}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred during login."}), 500


@auth_bp.route("/refresh", methods=["POST"])
def refresh() -> Tuple[Response, int]:
    """Rotate the user's refresh token and issue a new access token.

    Validates signature, expiry, type=refresh, and non-revoked DB status. Revokes the
    old refresh token and inserts a new one (Token Rotation).

    JSON Body:
        refresh_token (str): The raw refresh token.

    Returns:
        200: new tokens and expiry on success.
        401: on validation or revocation failure.
    """
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({"success": False, "error": "Refresh token is required."}), 400

    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return jsonify({"success": False, "error": "Invalid or expired refresh token."}), 401

    user_id = payload.get("sub")
    token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

    # Find the token record in the database
    token_record = RefreshToken.query.filter_by(token_hash=token_hash).first()
    if not token_record or token_record.revoked:
        logger.warning("Refresh failed: Token record not found or already revoked.")
        return jsonify({"success": False, "error": "Invalid or revoked refresh token."}), 401

    # Verify user is active
    user = User.query.filter_by(id=user_id).first()
    if not user or not user.is_active:
        return jsonify({"success": False, "error": "User account is disabled or not found."}), 403

    try:
        # Revoke the used refresh token
        token_record.revoked = True

        # Generate new pair of tokens
        new_access = generate_access_token(user_id)
        new_refresh = generate_refresh_token(user_id)

        # Hash and store new refresh token
        new_token_hash = hashlib.sha256(new_refresh.encode("utf-8")).hexdigest()
        new_refresh_payload = jwt.decode(new_refresh, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        new_expires_at = datetime.fromtimestamp(new_refresh_payload["exp"], tz=timezone.utc)

        db_new_refresh = RefreshToken(
            user_id=user_id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
            revoked=False,
        )
        db.session.add(db_new_refresh)
        db.session.commit()

        logger.info(f"Token rotated successfully for user ID {user_id}")

        return jsonify({
            "success": True,
            "access_token": new_access,
            "refresh_token": new_refresh,
            "access_expires_at": jwt.decode(new_access, Config.JWT_SECRET_KEY, algorithms=["HS256"])["exp"],
            "refresh_expires_at": new_refresh_payload["exp"],
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to rotate refresh token: {exc}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred during token refresh."}), 500


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout() -> Tuple[Response, int]:
    """Log out a user by revoking their refresh token.

    JSON Body:
        refresh_token (str): The refresh token to revoke.

    Returns:
        200: success message.
    """
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({"success": False, "error": "Refresh token is required."}), 400

    token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    token_record = RefreshToken.query.filter_by(token_hash=token_hash, user_id=g.current_user.id).first()

    if token_record:
        try:
            token_record.revoked = True
            db.session.commit()
            logger.info(f"Refresh token successfully revoked for user ID {g.current_user.id}")
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Failed to revoke token during logout: {exc}", exc_info=True)
            return jsonify({"success": False, "error": "An internal database error occurred."}), 500

    return jsonify({"success": True, "message": "Successfully logged out."}), 200


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me() -> Tuple[Response, int]:
    """Retrieve the current user's profile.

    Returns:
        200: current user's profile data.
    """
    user = g.current_user
    return jsonify({
        "success": True,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    }), 200


@auth_bp.route("/change-password", methods=["POST"])
@require_auth
def change_password() -> Tuple[Response, int]:
    """Change the user's password.

    Verifies the current password, validates the new password strength, updates
    the password hash, and revokes all active refresh tokens for the user to force
    re-login on all devices.

    JSON Body:
        current_password (str): The current plaintext password.
        new_password (str): The new plaintext password.

    Returns:
        200: success message.
        400/401: error message on verification or strength validation failure.
    """
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"success": False, "error": "Current password and new password are required."}), 400

    user = g.current_user
    if not verify_password(current_password, user.password_hash):
        return jsonify({"success": False, "error": "Invalid current password."}), 401

    is_strong, strength_err = validate_password_strength(new_password)
    if not is_strong:
        return jsonify({"success": False, "error": strength_err}), 400

    try:
        # Update user's password hash
        user.password_hash = hash_password(new_password)

        # Revoke all of the user's refresh tokens
        RefreshToken.query.filter_by(user_id=user.id).update({RefreshToken.revoked: True})
        db.session.commit()

        logger.info(f"Password changed and all sessions revoked for user {user.username} ({user.id})")

        return jsonify({
            "success": True,
            "message": "Password changed successfully. All sessions have been revoked. Please log in again."
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to change password for user ID {user.id}: {exc}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred while changing password."}), 500
