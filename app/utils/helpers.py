import os
import uuid
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger("helpers")

def generate_video_id() -> str:
    """Generate a unique identifier for a video upload."""
    return str(uuid.uuid4())

def safe_delete_file(file_path: str | Path) -> bool:
    """
    Safely delete a file from the filesystem if it exists.
    
    Args:
        file_path: Absolute path or Path object of the file to delete.
        
    Returns:
        True if deleted successfully or file does not exist, False otherwise.
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            logger.info(f"Successfully deleted temporary file: {path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {str(e)}", exc_info=True)
        return False

def clean_directory_contents(directory_path: str | Path) -> None:
    """
    Delete all files within a directory but keep the directory itself.
    Useful for cleaning up temp folders.
    """
    try:
        dir_path = Path(directory_path)
        if dir_path.exists() and dir_path.is_dir():
            for item in dir_path.iterdir():
                if item.is_file():
                    safe_delete_file(item)
            logger.info(f"Cleaned contents of directory: {dir_path}")
    except Exception as e:
        logger.error(f"Error cleaning directory {directory_path}: {str(e)}", exc_info=True)
