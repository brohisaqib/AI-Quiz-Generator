"""Password reset routes blueprint.

Defines endpoints for requesting a password reset token and resetting the password.
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Tuple

from flask import Blueprint, jsonify, request, Response
from flask_mail import Message

from app import mail
from app.config.settings import Config
from app.models import db
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.utils.auth import (
    hash_password,
    validate_password_strength,
)
from app.utils.logger import get_logger

logger = get_logger("password_reset_routes")

# Create the password reset blueprint
password_reset_bp = Blueprint("password_reset", __name__, url_prefix="/auth")


@password_reset_bp.route("/forgot-password", methods=["POST"])
def forgot_password() -> Tuple[Response, int]:
    """Request a password reset link.

    Generates a secure token, hashes it, stores it in the database with an expiration,
    and either emails the reset link or logs it depending on environment configuration.
    Always returns a generic success message to prevent user enumeration.

    JSON Body:
        email (str): The email address of the user.

    Returns:
        200: A generic success message.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400

    # Look up the user by email
    user = User.query.filter_by(email=email).first()

    # Generic response message
    success_message = "If that email is registered, a password reset link has been sent."

    if not user or not user.is_active:
        # User not found or inactive, but we still return the same success message
        logger.info(f"Password reset requested for unregistered or inactive email: {email}")
        return jsonify({"success": True, "message": success_message}), 200

    try:
        # Generate raw token
        raw_token = secrets.token_urlsafe(32)

        # Hash the token before storing
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Set expiry for 15 minutes from now
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Save to database
        reset_token_rec = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        db.session.add(reset_token_rec)
        db.session.commit()

        # Build reset link
        reset_link = f"{Config.FRONTEND_URL}/reset-password?token={raw_token}"

        # Determine if we should send a real email or fallback to logging
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            # Fallback dev mode logging (crucial for local testing)
            logger.info(f"[DEV MODE] Password reset link: {reset_link}")
        else:
            # Send real email using Flask-Mail
            msg = Message(
                subject="Password Reset Request",
                sender=Config.MAIL_DEFAULT_SENDER or "noreply@example.com",
                recipients=[user.email]
            )
            msg.body = (
                f"Hello,\n\n"
                f"You requested a password reset for your account. Please use the following link to reset your password:\n\n"
                f"{reset_link}\n\n"
                f"This link will expire in 15 minutes.\n\n"
                f"If you did not request this change, please ignore this email."
            )
            mail.send(msg)
            logger.info(f"Password reset email sent successfully to user {user.username} ({user.id})")

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to generate or send password reset for email {email}: {exc}", exc_info=True)
        # Even on failure, do not leak backend failure to user for security consistency
        return jsonify({"success": True, "message": success_message}), 200

    return jsonify({"success": True, "message": success_message}), 200


@password_reset_bp.route("/reset-password", methods=["POST"])
def reset_password() -> Tuple[Response, int]:
    """Reset a user's password using a valid reset token.

    Verifies the hashed token against the database, checks for expiration and usage status,
    validates the new password strength, updates the password hash, marks the token as used,
    and revokes all active refresh tokens for the user.

    JSON Body:
        token (str): The raw password reset token from the email/link.
        new_password (str): The new plaintext password.

    Returns:
        200: Success message on password reset.
        400: Error message if the token is invalid/expired or if password verification fails.
        500: Internal server error.
    """
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token", "").strip()
    new_password = data.get("new_password", "")

    if not raw_token or not new_password:
        return jsonify({"success": False, "error": "Token and new password are required."}), 400

    # Hash the raw token to look up the DB entry
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Look up matching row
    token_record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if not token_record or token_record.used or token_record.expires_at < now:
        return jsonify({
            "success": False,
            "error": "This password reset link is invalid or has expired. Please request a new one."
        }), 400

    # Validate new password strength
    is_strong, strength_err = validate_password_strength(new_password)
    if not is_strong:
        return jsonify({"success": False, "error": strength_err}), 400

    user = token_record.user
    if not user or not user.is_active:
        return jsonify({"success": False, "error": "The user associated with this token is inactive or not found."}), 400

    try:
        # Update user password
        user.password_hash = hash_password(new_password)

        # Mark token as used
        token_record.used = True

        # Revoke all of the user's refresh tokens to force re-login on all devices
        RefreshToken.query.filter_by(user_id=user.id).update({RefreshToken.revoked: True})

        db.session.commit()
        logger.info(f"Password reset successfully for user {user.username} ({user.id}) via token {token_record.id}")

        return jsonify({
            "success": True,
            "message": "Your password has been reset successfully. Please log in with your new password."
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to reset password for user ID {user.id} via token {token_record.id}: {exc}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred while resetting your password."}), 500
