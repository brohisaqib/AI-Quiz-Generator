import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, g, jsonify, request, send_file, Response

from app.api import api_bp
from app.config.settings import Config
from app.models import db
from app.models.quiz_result import QuizResult
from app.models.video_job import VideoJob
from app.services.audio_service import AudioService
from app.services.evaluation_service import EvaluationService
from app.services.pdf_service import PDFService
from app.services.quiz_service import QuizService
from app.services.summary_service import SummaryService
from app.services.upload_service import UploadService
from app.services.web_search_service import WebSearchService
from app.services.whisper_service import WhisperService
from app.services.youtube_service import YouTubeService
from app.utils.auth import require_auth
from app.utils.helpers import safe_delete_file
from app.utils.logger import get_logger
from app.utils.openai_error_handler import OpenAIServiceError

logger = get_logger("routes")

# Record the application startup time for uptime calculation
START_TIME = time.time()

# Service singletons to prevent startup crashes when configurations are missing
_services: Dict[str, Any] = {}


def get_service(name: str, service_class: Any) -> Any:
    """Retrieve or initialize a service singleton.

    Args:
        name: The service identifier key.
        service_class: The class to instantiate if not already present.

    Returns:
        The service singleton instance.
    """
    if name not in _services:
        _services[name] = service_class()
    return _services[name]


def _build_quiz_response(quiz_result: Any, summary: str, evaluation_result: Any) -> Dict[str, Any]:
    """Build the shared, canonical JSON response shape used by the API.

    Args:
        quiz_result: A QuizResponse Pydantic model instance.
        summary: The generated educational summary string.
        evaluation_result: A QuizEvaluation Pydantic model instance.

    Returns:
        A dictionary matching the response contract.
    """
    questions_list = []
    for q in quiz_result.questions:
        questions_list.append({
            "question": q.question,
            "options": q.options,
            "answer": q.answer,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "topic": q.topic,
        })

    return {
        "success": True,
        "title": quiz_result.title,
        "summary": summary,
        "questions": questions_list,
        "evaluation": {
            "score": evaluation_result.score,
            "feedback": evaluation_result.feedback,
        },
    }


def _persist_quiz_to_db(
    user_id: Any,
    original_filename: Optional[str],
    stored_path: Optional[str],
    source_type: str,
    title: str,
    summary: str,
    quiz_json: List[Dict[str, Any]],
    evaluation_score: float,
    evaluation_feedback: str,
    transcript: str,
) -> Optional[str]:
    """Helper to persist a quiz generation result to the PostgreSQL database.

    Creates both a VideoJob record and a QuizResult record. Returns the created
    QuizResult ID on success, or None if the save fails.

    Args:
        user_id: The authenticated User ID.
        original_filename: The name of the processed file or None.
        stored_path: The disk storage location path or None.
        source_type: The source category ("video"|"pdf"|"topic").
        title: The educational quiz title.
        summary: The generated summary.
        quiz_json: The list of quiz questions.
        evaluation_score: The quality score.
        evaluation_feedback: Feedback from G-Eval.
        transcript: The extracted source content.

    Returns:
        The UUID string of the QuizResult if committed, or None.
    """
    # Safeguard against non-nullable constraint in VideoJob.original_filename
    safe_filename = original_filename if original_filename is not None else "N/A"

    try:
        # 1. Create the VideoJob row
        video_job = VideoJob(
            user_id=user_id,
            original_filename=safe_filename,
            stored_path=stored_path,
            source_type=source_type,
        )
        db.session.add(video_job)
        db.session.flush()  # Populate video_job.id for foreign key reference

        # 2. Create the QuizResult row
        quiz_result = QuizResult(
            user_id=user_id,
            video_job_id=video_job.id,
            title=title,
            summary=summary,
            quiz_json=quiz_json,
            evaluation_score=evaluation_score,
            evaluation_feedback=evaluation_feedback,
            transcript=transcript,
        )
        db.session.add(quiz_result)
        db.session.commit()

        logger.info(f"Successfully persisted VideoJob {video_job.id} and QuizResult {quiz_result.id} to PostgreSQL DB.")
        return str(quiz_result.id)

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f"PostgreSQL database persistence failed for quiz '{title}': {exc}. "
            "Proceeding with returning response payload to user.",
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Video Upload
# ---------------------------------------------------------------------------

@api_bp.route("/upload-video", methods=["POST"])
@require_auth
def upload_video() -> Any:
    """Endpoint to upload a video file.

    Validates file extension, MIME type, and size.
    Saves the file to the configured uploads folder.

    Returns:
        A JSON response and HTTP status code.
    """
    logger.info("Received request to /upload-video")

    if "file" not in request.files:
        logger.warning("Upload failed: No file part in the request")
        return jsonify({"success": False, "error": "No file part in the request"}), 400

    file = request.files["file"]

    try:
        result = get_service("upload", UploadService).handle_upload(file)
        return jsonify({
            "success": True,
            "video_id": result["video_id"],
            "filename": result["filename"],
            "message": "Video uploaded successfully",
        }), 201

    except ValueError as ve:
        logger.warning(f"Upload validation failed: {str(ve)}")
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to upload video due to an internal error"}), 500


# ---------------------------------------------------------------------------
# Video → Quiz (existing pipeline — preserved as-is)
# ---------------------------------------------------------------------------

@api_bp.route("/generate-quiz", methods=["POST"])
@require_auth
def generate_quiz() -> Any:
    """Endpoint to process the video, transcribe audio, generate summary,

    generate quiz questions, and evaluate quiz quality.
    Cleans up all intermediate files after processing.

    Returns:
        A JSON response and HTTP status code.
    """
    logger.info("Received request to /generate-quiz")

    # 1. Parse Input
    data = request.get_json()
    if not data or "video_id" not in data:
        logger.warning("Generate quiz failed: Missing video_id in request body")
        return jsonify({"success": False, "error": "Missing video_id in request body"}), 400

    video_id = data["video_id"]
    logger.info(f"Processing quiz generation for video ID: {video_id}")

    video_path = None
    audio_path = None
    chunk_paths = []

    start_time = time.time()

    try:
        # 2. Retrieve Video Path
        try:
            video_path = get_service("upload", UploadService).get_uploaded_file_path(video_id)
        except FileNotFoundError as fnf:
            logger.warning(f"Video file not found: {str(fnf)}")
            return jsonify({"success": False, "error": str(fnf)}), 404

        # 3. Extract Audio
        try:
            audio_path = get_service("audio", AudioService).extract_audio(video_path, video_id)
        except Exception as ae:
            logger.error(f"Audio extraction stage failed: {str(ae)}")
            return jsonify({"success": False, "error": f"Audio extraction failed: {str(ae)}"}), 422

        # 4. Chunk Audio
        try:
            chunk_paths = get_service("audio", AudioService).chunk_audio(audio_path, video_id)
        except Exception as ac:
            logger.error(f"Audio chunking stage failed: {str(ac)}")
            return jsonify({"success": False, "error": f"Audio chunking failed: {str(ac)}"}), 422

        # 5. Transcribe Audio (Whisper)
        try:
            transcription = get_service("whisper", WhisperService).transcribe_chunks(chunk_paths)
        except ValueError as ve:
            logger.warning(f"Whisper transcript empty: {str(ve)}")
            return jsonify({"success": False, "error": str(ve)}), 422
        except OpenAIServiceError as we:
            logger.error(f"Whisper transcription AI error: {str(we)}")
            return jsonify({"success": False, "error": str(we)}), we.status_code
        except Exception as we:
            logger.error(f"Whisper transcription failed: {str(we)}")
            return jsonify({"success": False, "error": f"Whisper transcription failed: {str(we)}"}), 502

        # 6. Generate Summary
        try:
            summary = get_service("summary", SummaryService).generate_summary(transcription)
        except OpenAIServiceError as se:
            return jsonify({"success": False, "error": str(se)}), se.status_code
        except Exception as se:
            logger.error(f"Summary generation failed: {str(se)}")
            return jsonify({"success": False, "error": f"Summary generation failed: {str(se)}"}), 502

        # 7. Generate Quiz
        try:
            quiz_result = get_service("quiz", QuizService).generate_quiz(summary, transcription)
        except OpenAIServiceError as qe:
            return jsonify({"success": False, "error": str(qe)}), qe.status_code
        except Exception as qe:
            logger.error(f"Quiz generation failed: {str(qe)}")
            return jsonify({"success": False, "error": f"Quiz generation/parsing failed: {str(qe)}"}), 502

        # 8. Evaluate Quiz
        try:
            evaluation_result = get_service("evaluation", EvaluationService).evaluate_quiz(
                transcription, summary, quiz_result
            )
        except OpenAIServiceError as ee:
            return jsonify({"success": False, "error": str(ee)}), ee.status_code
        except Exception as ee:
            logger.error(f"G-Eval quiz evaluation failed: {str(ee)}")
            return jsonify({"success": False, "error": f"Quiz evaluation failed: {str(ee)}"}), 502

        # 9. Build Structured JSON Response
        response_data = _build_quiz_response(quiz_result, summary, evaluation_result)

        # 10. Extract original filename
        stored_filename = Path(video_path).name
        if "_" in stored_filename:
            original_filename = stored_filename.split("_", 1)[1]
        else:
            original_filename = stored_filename

        # 11. Persist to PostgreSQL via SQLAlchemy (non-blocking on failure)
        quiz_id = _persist_quiz_to_db(
            user_id=g.current_user.id,
            original_filename=original_filename,
            stored_path=video_path,
            source_type="video",
            title=quiz_result.title,
            summary=summary,
            quiz_json=response_data["questions"],
            evaluation_score=evaluation_result.score,
            evaluation_feedback=evaluation_result.feedback,
            transcript=transcription,
        )

        response_data["quiz_id"] = quiz_id

        # 12. Persist to disk (offline backups)
        quiz_file_path = Config.OUTPUT_FOLDER / f"{video_id}_quiz.json"
        with open(quiz_file_path, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

        transcript_file_path = Config.OUTPUT_FOLDER / f"{video_id}_transcript.txt"
        with open(transcript_file_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        processing_time = time.time() - start_time
        logger.info(
            f"Successfully processed quiz for video ID: {video_id} "
            f"in {processing_time:.2f}s"
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Unexpected pipeline failure for video ID {video_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected pipeline error occurred: {str(e)}"}), 500

    finally:
        # Cleanup: Remove video, full WAV audio, and MP3 chunks from filesystem
        logger.info(f"Starting post-processing cleanup for video ID: {video_id}")
        if video_path:
            safe_delete_file(video_path)
        if audio_path:
            safe_delete_file(audio_path)
        for chunk in chunk_paths:
            safe_delete_file(chunk)
        logger.info(f"Cleanup finished for video ID: {video_id}")


# ---------------------------------------------------------------------------
# PDF → Quiz
# ---------------------------------------------------------------------------

@api_bp.route("/generate-quiz-from-pdf", methods=["POST"])
@require_auth
def generate_quiz_from_pdf() -> Any:
    """Accept a PDF file upload and run the full quiz-generation pipeline.

    Accepts multipart/form-data with a ``file`` field (PDF only).
    Validates extension and MIME type, saves to temp, extracts text via
    ``PDFService``, then runs the standard summary → quiz → evaluation pipeline.

    Returns the canonical quiz JSON response on success.
    Rejects scanned / image-only PDFs with HTTP 400.
    """
    logger.info("Received request to POST /generate-quiz-from-pdf")

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request. Send a PDF as 'file' field."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file selected or empty filename."}), 400

    filename: str = file.filename.strip()

    # Validate extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext != "pdf":
        return jsonify({"success": False, "error": "Only PDF files are accepted. Please upload a .pdf file."}), 400

    # Validate MIME type
    allowed_pdf_mimes = {"application/pdf", "application/x-pdf"}
    mime_type: str = file.content_type or ""
    if mime_type and mime_type not in allowed_pdf_mimes:
        return jsonify({
            "success": False,
            "error": f"Invalid MIME type '{mime_type}'. Expected 'application/pdf'.",
        }), 400

    # Save to temp directory
    job_id = str(uuid.uuid4())
    pdf_temp_path = Path(Config.TEMP_FOLDER) / f"{job_id}.pdf"
    start_time = time.time()

    try:
        file.save(str(pdf_temp_path))
        logger.info(f"PDF saved temporarily to: {pdf_temp_path}")

        # 1. Extract text from PDF
        try:
            pdf_text = get_service("pdf", PDFService).extract_text(str(pdf_temp_path))
        except ValueError as ve:
            # Scanned / image-only PDF — explicit rejection
            logger.warning(f"PDF text extraction rejected: {ve}")
            return jsonify({"success": False, "error": str(ve)}), 400
        except IOError as ioe:
            logger.error(f"PDF IO error: {ioe}", exc_info=True)
            return jsonify({"success": False, "error": str(ioe)}), 400

        # 2. Generate Summary
        try:
            summary = get_service("summary", SummaryService).generate_summary(pdf_text)
        except OpenAIServiceError as se:
            return jsonify({"success": False, "error": str(se)}), se.status_code
        except Exception as se:
            logger.error(f"Summary generation failed: {se}", exc_info=True)
            return jsonify({"success": False, "error": f"Summary generation failed: {se}"}), 502

        # 3. Generate Quiz
        try:
            quiz_result = get_service("quiz", QuizService).generate_quiz(summary, pdf_text)
        except OpenAIServiceError as qe:
            return jsonify({"success": False, "error": str(qe)}), qe.status_code
        except Exception as qe:
            logger.error(f"Quiz generation failed: {qe}", exc_info=True)
            return jsonify({"success": False, "error": f"Quiz generation failed: {qe}"}), 502

        # 4. Evaluate Quiz
        try:
            evaluation_result = get_service("evaluation", EvaluationService).evaluate_quiz(
                pdf_text, summary, quiz_result
            )
        except OpenAIServiceError as ee:
            return jsonify({"success": False, "error": str(ee)}), ee.status_code
        except Exception as ee:
            logger.error(f"Quiz evaluation failed: {ee}", exc_info=True)
            return jsonify({"success": False, "error": f"Quiz evaluation failed: {ee}"}), 502

        # 5. Build Response
        response_data = _build_quiz_response(quiz_result, summary, evaluation_result)

        # 6. Persist to PostgreSQL via SQLAlchemy
        quiz_id = _persist_quiz_to_db(
            user_id=g.current_user.id,
            original_filename=filename,
            stored_path=str(pdf_temp_path),
            source_type="pdf",
            title=quiz_result.title,
            summary=summary,
            quiz_json=response_data["questions"],
            evaluation_score=evaluation_result.score,
            evaluation_feedback=evaluation_result.feedback,
            transcript=pdf_text,
        )

        response_data["quiz_id"] = quiz_id

        # 7. Persist to outputs folder
        quiz_file_path = Config.OUTPUT_FOLDER / f"{job_id}_quiz.json"
        with open(quiz_file_path, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

        processing_time = time.time() - start_time
        logger.info(
            f"PDF quiz pipeline completed in {processing_time:.2f}s. Job ID: {job_id}"
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Unexpected error in PDF quiz pipeline: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {e}"}), 500

    finally:
        safe_delete_file(pdf_temp_path)
        logger.info(f"Temp PDF cleaned up: {pdf_temp_path}")


# ---------------------------------------------------------------------------
# Topic / Web Search → Quiz
# ---------------------------------------------------------------------------

@api_bp.route("/generate-quiz-from-topic", methods=["POST"])
@require_auth
def generate_quiz_from_topic() -> Any:
    """Accept a JSON body with a ``topic`` string and run the full pipeline.

    Accepts JSON: ``{"topic": "..."}``.
    Searches DuckDuckGo via ``WebSearchService``, then runs the standard
    summary → quiz → evaluation pipeline on the search results.

    Returns the canonical quiz JSON response on success.
    """
    logger.info("Received request to POST /generate-quiz-from-topic")

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Request body must be JSON with a 'topic' field."}), 400

    topic: str = data.get("topic", "").strip()
    if not topic:
        return jsonify({"success": False, "error": "The 'topic' field is required and cannot be empty."}), 400

    max_results: int = int(data.get("max_results", 5))
    max_results = max(1, min(max_results, 10))  # clamp to [1, 10]

    job_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # 1. Retrieve web search content
        try:
            search_text = get_service("web_search", WebSearchService).search_topic(
                topic, max_results=max_results
            )
        except ValueError as ve:
            logger.warning(f"Web search rejected: {ve}")
            return jsonify({"success": False, "error": str(ve)}), 400

        # 2. Generate Summary
        try:
            summary = get_service("summary", SummaryService).generate_summary(search_text)
        except OpenAIServiceError as se:
            return jsonify({"success": False, "error": str(se)}), se.status_code
        except Exception as se:
            logger.error(f"Summary generation failed: {se}", exc_info=True)
            return jsonify({"success": False, "error": f"Summary generation failed: {se}"}), 502

        # 3. Generate Quiz
        try:
            quiz_result = get_service("quiz", QuizService).generate_quiz(summary, search_text)
        except OpenAIServiceError as qe:
            return jsonify({"success": False, "error": str(qe)}), qe.status_code
        except Exception as qe:
            logger.error(f"Quiz generation failed: {qe}", exc_info=True)
            return jsonify({"success": False, "error": f"Quiz generation failed: {qe}"}), 502

        # 4. Evaluate Quiz
        try:
            evaluation_result = get_service("evaluation", EvaluationService).evaluate_quiz(
                search_text, summary, quiz_result
            )
        except OpenAIServiceError as ee:
            return jsonify({"success": False, "error": str(ee)}), ee.status_code
        except Exception as ee:
            logger.error(f"Quiz evaluation failed: {ee}", exc_info=True)
            return jsonify({"success": False, "error": f"Quiz evaluation failed: {ee}"}), 502

        # 5. Build Response
        response_data = _build_quiz_response(quiz_result, summary, evaluation_result)

        # 6. Persist to PostgreSQL via SQLAlchemy
        quiz_id = _persist_quiz_to_db(
            user_id=g.current_user.id,
            original_filename=None,
            stored_path=None,
            source_type="topic",
            title=quiz_result.title,
            summary=summary,
            quiz_json=response_data["questions"],
            evaluation_score=evaluation_result.score,
            evaluation_feedback=evaluation_result.feedback,
            transcript=search_text,
        )

        response_data["quiz_id"] = quiz_id

        # 7. Persist to outputs folder
        quiz_file_path = Config.OUTPUT_FOLDER / f"{job_id}_quiz.json"
        with open(quiz_file_path, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

        processing_time = time.time() - start_time
        logger.info(
            f"Topic quiz pipeline completed in {processing_time:.2f}s for '{topic}'. Job ID: {job_id}"
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Unexpected error in topic quiz pipeline: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {e}"}), 500


# ---------------------------------------------------------------------------
# YouTube → Quiz
# ---------------------------------------------------------------------------

@api_bp.route("/generate-quiz-from-youtube", methods=["POST"])
@require_auth
def generate_quiz_from_youtube() -> Any:
    """Accept a YouTube URL, download its audio, transcribe, summarize,

    generate a quiz, and evaluate it.
    Cleans up all intermediate files after processing.

    Returns:
        A JSON response and HTTP status code.
    """
    logger.info("Received request to /generate-quiz-from-youtube")

    # 1. Parse Input
    data = request.get_json(silent=True)
    if not data or "youtube_url" not in data:
        logger.warning("Generate quiz from youtube failed: Missing youtube_url in request body")
        return jsonify({"success": False, "error": "Missing youtube_url in request body"}), 400

    youtube_url = data["youtube_url"].strip()
    if not youtube_url:
        logger.warning("Generate quiz from youtube failed: Empty youtube_url")
        return jsonify({"success": False, "error": "The 'youtube_url' field is required and cannot be empty."}), 400

    video_id = str(uuid.uuid4())
    logger.info(f"Processing quiz generation from YouTube: {youtube_url} with ID: {video_id}")

    audio_path = None
    chunk_paths = []
    start_time = time.time()

    try:
        # 2. Download YouTube audio
        try:
            audio_path = get_service("youtube", YouTubeService).download_audio(youtube_url, video_id)
        except ValueError as ve:
            logger.warning(f"YouTube download validation failed: {str(ve)}")
            return jsonify({"success": False, "error": str(ve)}), 400
        except Exception as e:
            logger.error(f"YouTube download failed: {str(e)}", exc_info=True)
            return jsonify({"success": False, "error": f"YouTube download failed: {str(e)}"}), 400

        # 3. Chunk Audio
        try:
            chunk_paths = get_service("audio", AudioService).chunk_audio(audio_path, video_id)
        except Exception as ac:
            logger.error(f"Audio chunking stage failed: {str(ac)}")
            return jsonify({"success": False, "error": f"Audio chunking failed: {str(ac)}"}), 422

        # 4. Transcribe Audio (Whisper)
        try:
            transcription = get_service("whisper", WhisperService).transcribe_chunks(chunk_paths)
        except ValueError as ve:
            logger.warning(f"Whisper transcript empty: {str(ve)}")
            return jsonify({"success": False, "error": str(ve)}), 422
        except OpenAIServiceError as we:
            logger.error(f"Whisper transcription AI error: {str(we)}")
            return jsonify({"success": False, "error": str(we)}), we.status_code
        except Exception as we:
            logger.error(f"Whisper transcription failed: {str(we)}")
            return jsonify({"success": False, "error": f"Whisper transcription failed: {str(we)}"}), 502

        # 5. Generate Summary
        try:
            summary = get_service("summary", SummaryService).generate_summary(transcription)
        except OpenAIServiceError as se:
            return jsonify({"success": False, "error": str(se)}), se.status_code
        except Exception as se:
            logger.error(f"Summary generation failed: {str(se)}")
            return jsonify({"success": False, "error": f"Summary generation failed: {str(se)}"}), 502

        # 6. Generate Quiz
        try:
            quiz_result = get_service("quiz", QuizService).generate_quiz(summary, transcription)
        except OpenAIServiceError as qe:
            return jsonify({"success": False, "error": str(qe)}), qe.status_code
        except Exception as qe:
            logger.error(f"Quiz generation failed: {str(qe)}")
            return jsonify({"success": False, "error": f"Quiz generation/parsing failed: {str(qe)}"}), 502

        # 7. Evaluate Quiz
        try:
            evaluation_result = get_service("evaluation", EvaluationService).evaluate_quiz(
                transcription, summary, quiz_result
            )
        except OpenAIServiceError as ee:
            return jsonify({"success": False, "error": str(ee)}), ee.status_code
        except Exception as ee:
            logger.error(f"G-Eval quiz evaluation failed: {str(ee)}")
            return jsonify({"success": False, "error": f"Quiz evaluation failed: {str(ee)}"}), 502

        # 8. Build Structured JSON Response
        response_data = _build_quiz_response(quiz_result, summary, evaluation_result)

        # 9. Persist to PostgreSQL via SQLAlchemy
        quiz_id = _persist_quiz_to_db(
            user_id=g.current_user.id,
            original_filename=youtube_url,
            stored_path=None,
            source_type="youtube",
            title=quiz_result.title,
            summary=summary,
            quiz_json=response_data["questions"],
            evaluation_score=evaluation_result.score,
            evaluation_feedback=evaluation_result.feedback,
            transcript=transcription,
        )

        response_data["quiz_id"] = quiz_id

        # 10. Persist to disk (offline backups)
        quiz_file_path = Config.OUTPUT_FOLDER / f"{video_id}_quiz.json"
        with open(quiz_file_path, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)

        transcript_file_path = Config.OUTPUT_FOLDER / f"{video_id}_transcript.txt"
        with open(transcript_file_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        processing_time = time.time() - start_time
        logger.info(
            f"Successfully processed quiz for YouTube URL: {youtube_url} "
            f"in {processing_time:.2f}s"
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Unexpected pipeline failure for YouTube URL {youtube_url}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected pipeline error occurred: {str(e)}"}), 500

    finally:
        # Cleanup: Remove full WAV audio and MP3 chunks from filesystem
        logger.info(f"Starting post-processing cleanup for YouTube ID: {video_id}")
        if audio_path:
            safe_delete_file(audio_path)
        for chunk in chunk_paths:
            safe_delete_file(chunk)
        logger.info(f"Cleanup finished for YouTube ID: {video_id}")


# ---------------------------------------------------------------------------
# Quiz retrieval, listing, and deletion
# ---------------------------------------------------------------------------

@api_bp.route("/quizzes", methods=["GET"])
@require_auth
def get_all_quizzes() -> Tuple[Response, int]:
    """Retrieve all quiz results generated by the current authenticated user.

    Returns a list of quizzes containing metadata, evaluation score, and source type
    from the joined VideoJob, ordered by creation date descending.

    Returns:
        200: JSON list of user's quizzes.
        500: JSON error message on retrieval failure.
    """
    try:
        user_id = g.current_user.id
        results = (
            db.session.query(QuizResult)
            .outerjoin(VideoJob, QuizResult.video_job_id == VideoJob.id)
            .filter(QuizResult.user_id == user_id)
            .order_by(QuizResult.created_at.desc())
            .all()
        )

        quizzes_list = []
        for row in results:
            source_type = row.video_job.source_type if row.video_job else "unknown"
            question_count = len(row.quiz_json) if isinstance(row.quiz_json, list) else 0

            quizzes_list.append({
                "id": str(row.id),
                "title": row.title,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "question_count": question_count,
                "evaluation_score": row.evaluation_score,
                "source_type": source_type,
            })

        return jsonify({
            "success": True,
            "quizzes": quizzes_list,
        }), 200

    except Exception as e:
        logger.error(f"Failed to fetch quizzes: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to retrieve quizzes."}), 500


@api_bp.route("/quiz/<id>", methods=["GET"])
@require_auth
def get_quiz(id: str) -> Tuple[Response, int]:
    """Retrieve a specific saved quiz by its unique ID.

    Enforces ownership by returning 404 if the quiz does not exist or
    does not belong to the current authenticated user.

    Args:
        id: The unique UUID string of the quiz result.

    Returns:
        200: JSON quiz structure.
        404: if the quiz is not found or not owned.
    """
    try:
        user_id = g.current_user.id
        quiz = QuizResult.query.filter_by(id=id, user_id=user_id).first()
        if not quiz:
            logger.warning(f"Fetch failed: Quiz {id} not found or not owned by user {user_id}.")
            return jsonify({"success": False, "error": "Quiz not found."}), 404

        return jsonify({
            "success": True,
            "quiz_id": str(quiz.id),
            "title": quiz.title,
            "summary": quiz.summary,
            "questions": quiz.quiz_json,
            "evaluation": {
                "score": quiz.evaluation_score,
                "feedback": quiz.evaluation_feedback,
            },
        }), 200

    except Exception as e:
        logger.error(f"Failed to fetch quiz {id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to retrieve quiz."}), 500


@api_bp.route("/quiz/<id>", methods=["DELETE"])
@require_auth
def delete_quiz(id: str) -> Tuple[Response, int]:
    """Delete a specific saved quiz by its unique ID.

    Enforces ownership by returning 404 if the quiz does not exist or
    does not belong to the current authenticated user to prevent leakage.

    Args:
        id: The unique UUID string of the quiz result to delete.

    Returns:
        200: JSON success status.
        404: if the quiz is not found or not owned.
    """
    try:
        user_id = g.current_user.id
        quiz = QuizResult.query.filter_by(id=id, user_id=user_id).first()
        if not quiz:
            logger.warning(f"Delete failed: Quiz {id} not found or not owned by user {user_id}.")
            return jsonify({"success": False, "error": "Quiz not found."}), 404

        db.session.delete(quiz)
        db.session.commit()
        logger.info(f"Quiz {id} successfully deleted by user {user_id}.")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete quiz {id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to delete quiz."}), 500


@api_bp.route("/transcript/<id>", methods=["GET"])
@require_auth
def get_transcript(id: str) -> Tuple[Response, int]:
    """Retrieve the saved transcript text for a specific quiz by its ID.

    Enforces ownership by returning 404 if the quiz does not exist or
    does not belong to the current authenticated user.

    Args:
        id: The unique UUID string of the quiz result.

    Returns:
        200: JSON response with transcript text.
        404: if the transcript is not found or not owned.
    """
    try:
        user_id = g.current_user.id
        quiz = QuizResult.query.filter_by(id=id, user_id=user_id).first()
        if not quiz:
            logger.warning(f"Fetch failed: Transcript for quiz {id} not found or not owned by user {user_id}.")
            return jsonify({"success": False, "error": "Transcript not found."}), 404

        return jsonify({
            "success": True,
            "quiz_id": str(quiz.id),
            "transcript": quiz.transcript,
        }), 200

    except Exception as e:
        logger.error(f"Failed to fetch transcript for quiz {id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to retrieve transcript."}), 500


@api_bp.route("/download/<id>", methods=["GET"])
@require_auth
def download_quiz(id: str) -> Tuple[Response, int]:
    """Generate a downloadable JSON attachment file of the quiz.

    Enforces ownership by returning 404 if the quiz does not exist or
    does not belong to the current authenticated user.

    Args:
        id: The unique UUID string of the quiz result.

    Returns:
        200: Attachment download stream.
        404: if the quiz is not found or not owned.
    """
    try:
        user_id = g.current_user.id
        quiz = QuizResult.query.filter_by(id=id, user_id=user_id).first()
        if not quiz:
            logger.warning(f"Download failed: Quiz {id} not found or not owned by user {user_id}.")
            return jsonify({"success": False, "error": "Quiz not found."}), 404

        quiz_data = {
            "success": True,
            "quiz_id": str(quiz.id),
            "title": quiz.title,
            "summary": quiz.summary,
            "questions": quiz.quiz_json,
            "evaluation": {
                "score": quiz.evaluation_score,
                "feedback": quiz.evaluation_feedback,
            },
        }

        # Convert to raw byte buffer for send_file
        quiz_str = json.dumps(quiz_data, indent=2, ensure_ascii=False)
        fp = io.BytesIO(quiz_str.encode("utf-8"))

        return send_file(
            fp,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{quiz.title.replace(' ', '_')}_quiz.json",
        )

    except Exception as e:
        logger.error(f"Failed to download quiz {id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to download quiz."}), 500


# ---------------------------------------------------------------------------
# Health Check (public — no auth required)
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health() -> Tuple[Response, int]:
    """Health check endpoint returning system status, version, and uptime.

    This endpoint is intentionally public (no auth required).

    Returns:
        200: JSON status payload.
    """
    uptime_seconds = time.time() - START_TIME

    # Format uptime nicely
    days = int(uptime_seconds // (24 * 3600))
    hours = int((uptime_seconds % (24 * 3600)) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)

    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "uptime": uptime_str,
    }), 200
