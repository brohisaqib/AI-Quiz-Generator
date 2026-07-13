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
