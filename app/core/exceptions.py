class QuizGeneratorException(Exception):
    """Base exception for the AI Quiz Generator application."""
    pass

class VideoValidationError(QuizGeneratorException):
    """Exception raised when video validation fails."""
    pass

class AudioProcessingError(QuizGeneratorException):
    """Exception raised when audio extraction or chunking fails."""
    pass

class TranscriptionError(QuizGeneratorException):
    """Exception raised when audio transcription fails."""
    pass

class SummaryGenerationError(QuizGeneratorException):
    """Exception raised when summary generation fails."""
    pass

class QuizGenerationError(QuizGeneratorException):
    """Exception raised when quiz generation or parsing fails."""
    pass

class EvaluationError(QuizGeneratorException):
    """Exception raised when quiz evaluation fails."""
    pass

class ContentModerationError(QuizGeneratorException):
    """Exception raised when source content fails the moderation / guardrails check.

    Attributes:
        reason: A short, human-readable explanation of why the content was
            rejected (never contains the flagged text itself).
        status_code: HTTP status code to return to the client (always 400).
    """

    status_code: int = 400

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
