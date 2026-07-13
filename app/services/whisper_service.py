"""
Whisper Service (via Groq).

Stage 3: Transcription (Groq-hosted Whisper Large v3)
"""

from typing import List

import openai
from openai import OpenAI

from app.config.settings import Config
from app.utils.logger import get_logger
from app.utils.openai_error_handler import handle_openai_exception, OpenAIServiceError

logger = get_logger("whisper_service")


class WhisperService:
    """Service to transcribe audio chunks using Groq-hosted Whisper Large v3."""

    def __init__(self) -> None:
        api_key = Config.GROQ_API_KEY
        if not api_key:
            logger.error("Groq API key is missing in whisper service setup")
            raise ValueError("Groq API key is not configured. Please add GROQ_API_KEY to your .env file.")

        self.client = OpenAI(
            api_key=api_key,
            base_url=Config.GROQ_BASE_URL,
        )
        self.model = Config.GROQ_WHISPER_MODEL

    def _transcribe_chunk(self, chunk_path: str) -> str:
        try:
            with open(chunk_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                )
            text = response if isinstance(response, str) else getattr(response, "text", "")
            return text.strip()

        except openai.OpenAIError as exc:
            logger.error(f"Groq Whisper transcription failed for chunk {chunk_path}: {str(exc)}", exc_info=True)
            raise handle_openai_exception(exc, context="Groq Whisper transcription")
        except Exception as exc:
            logger.error(f"Unexpected error during transcription of {chunk_path}: {str(exc)}", exc_info=True)
            raise handle_openai_exception(exc, context="Groq Whisper transcription")

    def transcribe_chunks(self, chunk_paths: List[str]) -> str:
        """
        Transcribe a list of audio chunks and merge them into one transcript.

        Args:
            chunk_paths: Ordered list of audio chunk file paths.

        Returns:
            str: The merged, whitespace-normalized transcript.

        Raises:
            ValueError: If no chunks were provided or the merged transcript is empty.
            OpenAIServiceError: If a Groq call fails (rate limit, auth, timeout, etc.).
        """
        if not chunk_paths:
            logger.error("No audio chunks were provided for transcription")
            raise ValueError("No audio chunks were provided for transcription.")

        transcripts: List[str] = []
        for index, chunk_path in enumerate(chunk_paths):
            logger.info(f"Transcribing chunk {index + 1}/{len(chunk_paths)}: {chunk_path}")
            chunk_text = self._transcribe_chunk(chunk_path)
            if chunk_text:
                transcripts.append(chunk_text)

        merged_transcript = " ".join(transcripts).strip()

        if not merged_transcript:
            logger.error("Transcription completed but produced no usable text")
            raise ValueError("Transcription completed but produced no usable text.")

        logger.info(f"Transcription complete. Total length={len(merged_transcript)} characters.")
        return merged_transcript