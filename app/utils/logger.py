import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.config.settings import Config

# Ensure log directory is initialized
Config.ensure_directories_exist()

# Configure logger
logger = logging.getLogger("ai_quiz_generator")
logger.setLevel(logging.INFO)

# Formatter for logs
log_formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Avoid adding duplicate handlers if logger is already configured
if not logger.handlers:
    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating log file in the log folder)
    log_file_path = Path(Config.LOG_FOLDER) / "app.log"
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """Get a sub-logger under the primary application namespace."""
    return logging.getLogger(f"ai_quiz_generator.{name}")
