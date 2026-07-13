import os
from werkzeug.utils import secure_filename
from app.config.settings import Config
from app.utils.logger import get_logger

logger = get_logger("validators")

def is_allowed_file_extension(filename: str) -> bool:
    """Check if the file extension is allowed."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS

def validate_video_upload(filename: str, mime_type: str, file_size: int) -> tuple[bool, str]:
    """
    Validate the video file upload checking extension, size, and MIME type.
    
    Args:
        filename: Name of the uploaded file.
        mime_type: MIME type of the file.
        file_size: Size of the file in bytes.
        
    Returns:
        A tuple of (is_valid, error_message).
    """
    if not filename:
        return False, "Filename cannot be empty"
        
    # Check extension
    if not is_allowed_file_extension(filename):
        allowed_exts = ", ".join(Config.ALLOWED_EXTENSIONS)
        logger.warning(f"File validation failed. Invalid extension for file: {filename}")
        return False, f"Unsupported file extension. Allowed formats: {allowed_exts}"
        
    # Check MIME type if provided
    if mime_type and mime_type not in Config.ALLOWED_MIME_TYPES:
        allowed_mimes = ", ".join(Config.ALLOWED_MIME_TYPES)
        logger.warning(f"File validation failed. Invalid MIME type '{mime_type}' for file: {filename}")
        return False, f"Unsupported MIME type. Allowed MIME types: {allowed_mimes}"
        
    # Check file size
    if file_size <= 0:
        logger.warning(f"File validation failed. File is empty: {filename}")
        return False, "File is empty or corrupted"
        
    if file_size > Config.MAX_CONTENT_LENGTH:
        max_mb = Config.MAX_CONTENT_LENGTH / (1024 * 1024)
        logger.warning(f"File validation failed. File size {file_size} bytes exceeds limit of {Config.MAX_CONTENT_LENGTH} bytes for: {filename}")
        return False, f"File size exceeds maximum limit of {max_mb:.1f} MB"
        
    return True, ""
