import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file explicitly
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Configure early logging for config
import logging
logger = logging.getLogger("ai_quiz_generator.config")
if not logging.getLogger().handlers and not logger.handlers:
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        stream=sys.stdout
    )
logger.info(f"Loading .env from: {env_path} (exists={env_path.exists()})")

class Config:
    """Application configuration loading from environment variables."""
    
    # Flask settings
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = FLASK_ENV == "development"
    TESTING: bool = False
    
    # OpenAI Settings (kept for backward-compatibility)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL: str = os.getenv("GPT_MODEL", "gpt-4o")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # Groq API Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_CHAT_MODEL: str = os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")
    GROQ_EVAL_MODEL: str = os.getenv("GROQ_EVAL_MODEL", os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant"))
    GROQ_WHISPER_MODEL: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    
    # Directory Settings
    UPLOAD_FOLDER: Path = BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")
    TEMP_FOLDER: Path = BASE_DIR / os.getenv("TEMP_FOLDER", "temp")
    OUTPUT_FOLDER: Path = BASE_DIR / os.getenv("OUTPUT_FOLDER", "outputs")
    LOG_FOLDER: Path = BASE_DIR / os.getenv("LOG_FOLDER", "logs")

    # SQLite database path (relative to project root or absolute)
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "app.db"))

    # PostgreSQL Database URL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # File Upload Constraints
    # Default: 100MB
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_UPLOAD_SIZE", 104857600))
    
    # Supported Video Formats
    ALLOWED_EXTENSIONS: set = {"mp4", "mov", "avi", "mkv"}
    
    # Supported MIME types for videos
    ALLOWED_MIME_TYPES: set = {
        "video/mp4",
        "video/quicktime",  # mov
        "video/x-msvideo",  # avi
        "video/x-matroska", # mkv
    }
    
    # Whisper chunking configurations
    # Audio chunks should not exceed ~25MB for OpenAI Whisper API.
    # We target 10 minutes (~10MB to 15MB depending on quality) or 20MB chunk files.
    # Pydub splits by milliseconds, so 10 minutes = 10 * 60 * 1000 = 600,000 ms.
    AUDIO_CHUNK_DURATION_MS: int = 10 * 60 * 1000  # 10 minutes

    # -----------------------------------------------------------------------
    # Authentication Settings (JWT)
    # -----------------------------------------------------------------------
    # JWT_SECRET_KEY: long random string — generate with: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ACCESS_EXPIRY_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRY_MINUTES", "60"))
    JWT_REFRESH_EXPIRY_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRY_DAYS", "30"))

    # CORS allowed origins (comma-separated or "*" for dev)
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    @classmethod
    def ensure_directories_exist(cls) -> None:
        """Create necessary system directories if they don't exist."""
        for folder in [cls.UPLOAD_FOLDER, cls.TEMP_FOLDER, cls.OUTPUT_FOLDER, cls.LOG_FOLDER]:
            folder.mkdir(parents=True, exist_ok=True)
        # Also ensure the data directory exists for SQLite
        Path(cls.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_database_config(cls) -> None:
        """
        Validate database configuration on app startup.
        Raises RuntimeError if DATABASE_URL is empty and FLASK_ENV is production.
        Logs a warning otherwise.
        """
        import logging
        _logger = logging.getLogger("ai_quiz_generator.config")
        if not cls.DATABASE_URL:
            if cls.FLASK_ENV == "production":
                raise RuntimeError("DATABASE_URL is not set. Database connection is required in production.")
            else:
                _logger.warning(
                    "DATABASE_URL is empty. This is acceptable for development/testing, "
                    "but you will need to set DATABASE_URL to connect to a PostgreSQL database."
                )

    @classmethod
    def validate_auth_config(cls) -> None:
        """
        Log a startup warning if JWT_SECRET_KEY is missing.
        """
        import logging
        _logger = logging.getLogger("ai_quiz_generator.config")
        if not cls.JWT_SECRET_KEY:
            _logger.warning(
                "SECURITY WARNING: JWT_SECRET_KEY is not set. Token verification and "
                "auth routes will NOT work properly until this is configured in your .env file."
            )
