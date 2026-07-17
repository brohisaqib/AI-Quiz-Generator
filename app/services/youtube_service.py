"""
YouTube Service.

Stage 1: Downloader for YouTube URL to audio (WAV)
"""

import os
import re
from pathlib import Path
import yt_dlp

from app.config.settings import Config
from app.utils.logger import get_logger

logger = get_logger("youtube_service")


class YouTubeService:
    """Service to download audio streams from YouTube videos."""

    def __init__(self) -> None:
        Config.ensure_directories_exist()

    def download_audio(self, youtube_url: str, video_id: str) -> str:
        """
        Validate YouTube URL, check video duration, and download the audio stream.

        Args:
            youtube_url: The URL of the YouTube video to process.
            video_id: A unique ID to name the downloaded audio file.

        Returns:
            str: The absolute path to the downloaded WAV audio file.

        Raises:
            ValueError: If the URL is invalid, the video duration exceeds limits,
                        or the video is private/unavailable/age-restricted.
            RuntimeError: If downloading or post-processing fails.
        """
        logger.info(f"Processing YouTube URL: {youtube_url} with video ID: {video_id}")

        # 1. Validate URL
        yt_pattern = re.compile(
            r'^(https?://)?(www\.)?(m\.)?(youtube\.com|youtu\.be)/.+$'
        )
        if not yt_pattern.match(youtube_url):
            logger.error(f"Invalid YouTube URL format: {youtube_url}")
            raise ValueError("The provided URL is not a valid YouTube URL.")

        # 2. Extract metadata first to check duration
        ydl_opts_meta = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
        except Exception as e:
            logger.error(f"Failed to fetch metadata for URL {youtube_url}: {str(e)}", exc_info=True)
            self._handle_ytdlp_exception(e)

        if not info:
            logger.error(f"Could not retrieve video information for {youtube_url}")
            raise ValueError("Could not retrieve video information. The video may be unavailable.")

        # Check duration
        duration_seconds = info.get('duration')
        if duration_seconds is None:
            logger.warning(f"Could not determine video duration for {youtube_url}. Proceeding.")
        else:
            duration_minutes = duration_seconds / 60.0
            max_allowed = Config.MAX_YOUTUBE_DURATION_MINUTES
            if duration_minutes > max_allowed:
                logger.error(
                    f"Video duration {duration_minutes:.2f}m exceeds limit of {max_allowed}m"
                )
                raise ValueError(
                    f"The video duration ({duration_minutes:.1f} minutes) exceeds the maximum allowed duration of {max_allowed} minutes."
                )

        # 3. Download best audio stream as WAV
        audio_output_path = Path(Config.TEMP_FOLDER) / f"{video_id}_full_audio"
        
        ydl_opts_dl = {
            'format': 'bestaudio/best',
            'outtmpl': str(audio_output_path) + '.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            logger.info(f"Downloading YouTube audio to template: {audio_output_path}")
            with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                ydl.download([youtube_url])
        except Exception as e:
            logger.error(f"Failed to download YouTube audio for URL {youtube_url}: {str(e)}", exc_info=True)
            self._handle_ytdlp_exception(e)

        # Check that the wav file actually exists
        final_wav_path = Path(Config.TEMP_FOLDER) / f"{video_id}_full_audio.wav"
        if not final_wav_path.exists():
            logger.error(f"Expected output file does not exist: {final_wav_path}")
            raise RuntimeError("YouTube audio download failed: converted audio file was not created.")

        logger.info(f"Successfully downloaded and extracted audio to {final_wav_path}")
        return str(final_wav_path)

    def _handle_ytdlp_exception(self, exc: Exception) -> None:
        """Helper to parse yt-dlp exceptions and raise user-friendly errors."""
        err_msg = str(exc).lower()
        
        if "private" in err_msg:
            raise ValueError("This YouTube video is private or unavailable.")
        elif "sign in" in err_msg or "confirm your age" in err_msg or "age" in err_msg or "restricted" in err_msg:
            raise ValueError("This YouTube video is age-restricted and cannot be processed.")
        elif "region" in err_msg or "geo" in err_msg or "country" in err_msg or "blocked" in err_msg or "not available in your country" in err_msg:
            raise ValueError("This YouTube video is region-locked or geo-blocked.")
        elif "not found" in err_msg or "does not exist" in err_msg or "404" in err_msg or "unavailable" in err_msg:
            raise ValueError("This YouTube video is unavailable or could not be found.")
        else:
            raise ValueError(f"YouTube download failed: {str(exc)}")
