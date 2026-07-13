import os
from pathlib import Path
from moviepy import VideoFileClip
from pydub import AudioSegment
from app.config.settings import Config
from app.utils.logger import get_logger
from app.utils.helpers import safe_delete_file

logger = get_logger("audio_service")

class AudioService:
    """Service to handle audio extraction from video and chunking."""

    def __init__(self) -> None:
        Config.ensure_directories_exist()

    def extract_audio(self, video_path: str, video_id: str) -> str:
        """
        Extract the audio track from a video file and save it as a WAV file.
        
        Args:
            video_path: Absolute path to the source video file.
            video_id: Unique identifier for the video.
            
        Returns:
            The path to the extracted audio file.
            
        Raises:
            Exception: If audio extraction fails.
        """
        logger.info(f"Extracting audio for video ID: {video_id} from {video_path}")
        
        # Output audio file path in temporary directory
        audio_output_path = Path(Config.TEMP_FOLDER) / f"{video_id}_full_audio.wav"
        
        video_clip = None
        try:
            # Load video file
            video_clip = VideoFileClip(video_path)
            
            # Check if video has an audio track
            if video_clip.audio is None:
                logger.error(f"Video {video_path} does not contain an audio track")
                raise ValueError("The uploaded video file has no audio track.")
                
            # Write audio track to a WAV file
            # Use pcm_s16le codec for high compatibility WAV format
            video_clip.audio.write_audiofile(
                str(audio_output_path),
                codec="pcm_s16le",
                ffmpeg_params=["-ac", "1"],  # Convert to mono to reduce file size
                logger=None  # Silence moviepy logging
            )
            
            logger.info(f"Successfully extracted audio to: {audio_output_path}")
            return str(audio_output_path)
            
        except Exception as e:
            logger.error(f"Failed to extract audio from video {video_path}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Audio extraction failed: {str(e)}")
        finally:
            # Ensure clip is closed to release file handles in Windows
            if video_clip:
                try:
                    video_clip.close()
                except Exception as close_err:
                    logger.warning(f"Could not close VideoFileClip resource: {str(close_err)}")

    def chunk_audio(self, audio_path: str, video_id: str) -> list[str]:
        """
        Splits a single audio file into smaller chunks to meet OpenAI size constraints.
        
        Args:
            audio_path: Absolute path to the source audio file (WAV/MP3).
            video_id: Unique identifier for the video.
            
        Returns:
            List of paths to the audio chunks.
            
        Raises:
            Exception: If audio chunking fails.
        """
        logger.info(f"Splitting audio file {audio_path} into chunks")
        chunk_paths = []
        
        try:
            # Load audio using Pydub
            audio = AudioSegment.from_file(audio_path)
            duration_ms = len(audio)
            
            # If the audio is shorter than the configured duration limit, return it as a single chunk
            chunk_limit_ms = Config.AUDIO_CHUNK_DURATION_MS
            if duration_ms <= chunk_limit_ms:
                logger.info("Audio is short enough. No chunking required.")
                # We can just export it as a compressed mp3 to save upload bandwidth
                single_chunk_path = Path(Config.TEMP_FOLDER) / f"{video_id}_chunk_0.mp3"
                audio.export(str(single_chunk_path), format="mp3", bitrate="128k")
                return [str(single_chunk_path)]
            
            # Perform chunking
            num_chunks = (duration_ms + chunk_limit_ms - 1) // chunk_limit_ms
            logger.info(f"Audio duration: {duration_ms / 1000:.1f}s. Creating {num_chunks} chunks.")
            
            for i in range(num_chunks):
                start_ms = i * chunk_limit_ms
                end_ms = min(start_ms + chunk_limit_ms, duration_ms)
                
                chunk = audio[start_ms:end_ms]
                chunk_filename = f"{video_id}_chunk_{i}.mp3"
                chunk_output_path = Path(Config.TEMP_FOLDER) / chunk_filename
                
                # Export chunk as MP3 (mono, 128k is perfect balance of quality/size for Whisper)
                chunk.export(
                    str(chunk_output_path),
                    format="mp3",
                    bitrate="128k",
                    parameters=["-ac", "1"]
                )
                chunk_paths.append(str(chunk_output_path))
                logger.info(f"Exported chunk {i} ({start_ms/1000:.1f}s to {end_ms/1000:.1f}s) to {chunk_output_path}")
                
            return chunk_paths
            
        except Exception as e:
            logger.error(f"Failed to chunk audio {audio_path}: {str(e)}", exc_info=True)
            # Clean up any chunks created so far
            for path in chunk_paths:
                safe_delete_file(path)
            raise RuntimeError(f"Audio chunking failed: {str(e)}")
