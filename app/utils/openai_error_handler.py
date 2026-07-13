"""
Centralized error handling for AI provider (OpenAI/Groq) API calls.

Every service that calls an LLM or Whisper endpoint routes its exceptions
through `handle_openai_exception()` so that the backend NEVER lets a raw
SDK exception escape unhandled. Every failure is converted into an
`OpenAIServiceError` carrying a safe message and correct HTTP status code.
"""

import traceback

import openai
import groq

from app.utils.logger import get_logger

logger = get_logger("openai_error_handler")


class OpenAIServiceError(Exception):
    """Raised whenever an AI provider API call fails. Carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def handle_openai_exception(exc: Exception, context: str = "") -> OpenAIServiceError:
    """
    Convert any exception raised during an OpenAI/Groq API call into a safe,
    structured OpenAIServiceError. Always logs the full traceback so the
    real cause is never lost, even though the client only sees a clean
    message.

    Args:
        exc: The exception raised by the OpenAI/Groq SDK (or anything else).
        context: A short label identifying which call failed
                 (e.g. "Whisper transcription", "Quiz generation").

    Returns:
        OpenAIServiceError: Safe to re-raise; the Flask route will catch
        this and return it as JSON.
    """
    label = f" ({context})" if context else ""
    logger.error("AI provider call failed%s: %s", label, exc)
    logger.error(traceback.format_exc())

    # --- Rate limit / quota exceeded ---
    if isinstance(exc, (openai.RateLimitError, groq.RateLimitError)):
        return OpenAIServiceError(
            "Rate limit / quota exceeded on the AI provider. Please wait and try again.",
            status_code=429,
        )

    # --- Authentication failure ---
    if isinstance(exc, (openai.AuthenticationError, groq.AuthenticationError)):
        return OpenAIServiceError(
            "AI provider authentication failed. Please check your API key.",
            status_code=401,
        )

    # --- Request timeout ---
    if isinstance(exc, (openai.APITimeoutError, groq.APITimeoutError)):
        return OpenAIServiceError(
            "AI provider request timed out. Please try again.",
            status_code=504,
        )

    # --- Bad request (invalid params, malformed input, etc.) ---
    if isinstance(exc, (openai.BadRequestError, groq.BadRequestError)):
        return OpenAIServiceError(
            f"AI provider rejected the request: {exc}",
            status_code=400,
        )

    # --- Connection issues ---
    if isinstance(exc, (openai.APIConnectionError, groq.APIConnectionError)):
        return OpenAIServiceError(
            "Failed to connect to the AI provider. Please check your internet connection.",
            status_code=502,
        )

    # --- Any other generic API error ---
    if isinstance(exc, (openai.APIError, groq.APIError)):
        return OpenAIServiceError(
            f"AI provider API error: {exc}",
            status_code=502,
        )

    # --- Anything else (bugs, unexpected SDK/network errors) — still never crash ---
    return OpenAIServiceError(
        f"An unexpected error occurred while calling the AI provider: {exc}",
        status_code=500,
    )