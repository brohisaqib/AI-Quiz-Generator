import os
from pathlib import Path
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from app.config.settings import Config
from app.utils.validators import validate_video_upload
from app.utils.helpers import generate_video_id
from app.utils.logger import get_logger

logger = get_logger("upload_service")

class UploadService:
    """Service to handle video upload and validation."""

    def __init__(self) -> None:
        Config.ensure_directories_exist()

    def handle_upload(self, file: FileStorage) -> dict:
        """
        Validates and saves the uploaded video file.
        
        Args:
            file: The FileStorage object from Flask request.
            
        Returns:
            A dict containing video_id, filename, and file_path if successful.
            
        Raises:
            ValueError: If validation fails.
            IOError: If saving the file fails.
        """
        if not file or not file.filename:
            logger.error("Upload failed: No file selected or empty file object.")
            raise ValueError("No file uploaded or file is empty")

        filename = secure_filename(file.filename)
        mime_type = file.content_type
        
        # Get file size safely without loading everything in memory
        try:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset pointer back to the beginning
        except Exception as e:
            logger.error(f"Failed to determine file size for {filename}: {str(e)}")
            raise ValueError("Could not determine uploaded file size")

        # Validate file
        is_valid, error_msg = validate_video_upload(filename, mime_type, file_size)
        if not is_valid:
            logger.warning(f"Upload validation failed for {filename}: {error_msg}")
            raise ValueError(error_msg)

        # Generate a unique video ID
        video_id = generate_video_id()
        
        # Formulate safe storage name: <video_id>_<secure_name>
        stored_filename = f"{video_id}_{filename}"
        dest_path = Path(Config.UPLOAD_FOLDER) / stored_filename

        try:
            file.save(str(dest_path))
            logger.info(f"Video uploaded successfully. ID: {video_id}, Size: {file_size} bytes, Path: {dest_path}")
        except Exception as e:
            logger.error(f"Failed to save file {filename} to {dest_path}: {str(e)}", exc_info=True)
            raise IOError("Internal server error saving the file")

        return {
            "video_id": video_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "file_path": str(dest_path)
        }

    def get_uploaded_file_path(self, video_id: str) -> str:
        """
        Locate the stored video path using its unique video_id.
        
        Args:
            video_id: The unique identifier generated during upload.
            
        Returns:
            The absolute path to the video file.
            
        Raises:
            FileNotFoundError: If no file matching the ID is found.
        """
        upload_dir = Path(Config.UPLOAD_FOLDER)
        # Search for file starting with the video_id prefix
        matches = list(upload_dir.glob(f"{video_id}_*"))
        
        if not matches:
            logger.warning(f"No video file found matching ID: {video_id}")
            raise FileNotFoundError(f"Video not found for ID: {video_id}")
            
        # Return the first matching file path
        return str(matches[0].resolve())
