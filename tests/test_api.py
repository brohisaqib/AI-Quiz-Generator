import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
import json
from pathlib import Path
from app.config.settings import Config
from app.schemas.quiz import QuizResponse, QuizQuestion, QuizEvaluation

def test_health_endpoint(client):
    """Test health status endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime" in data

@patch("app.services.upload_service.UploadService.handle_upload")
def test_upload_video_endpoint_success(mock_handle, client):
    """Test uploading a valid video file."""
    mock_handle.return_value = {
        "video_id": "test-uuid-123",
        "filename": "sample.mp4",
        "stored_filename": "test-uuid-123_sample.mp4",
        "file_path": "/fake/path/test-uuid-123_sample.mp4"
    }
    
    # Create fake video file payload
    data = {
        "file": (BytesIO(b"dummy video content"), "sample.mp4")
    }
    response = client.post(
        "/upload-video",
        data=data,
        content_type="multipart/form-data"
    )
    assert response.status_code == 201
    assert response.json["video_id"] == "test-uuid-123"
    assert "message" in response.json

def test_upload_video_no_file(client):
    """Test uploading with missing file field."""
    response = client.post("/upload-video", data={})
    assert response.status_code == 400
    assert "error" in response.json

@patch("app.services.upload_service.UploadService.get_uploaded_file_path")
@patch("app.services.audio_service.AudioService.extract_audio")
@patch("app.services.audio_service.AudioService.chunk_audio")
@patch("app.services.whisper_service.WhisperService.transcribe_chunks")
@patch("app.services.summary_service.SummaryService.generate_summary")
@patch("app.services.quiz_service.QuizService.generate_quiz")
@patch("app.services.evaluation_service.EvaluationService.evaluate_quiz")
def test_generate_quiz_pipeline(
    mock_evaluate, mock_quiz, mock_summary, mock_transcribe, 
    mock_chunk, mock_extract, mock_get_path, client
):
    """Test the complete end-to-end quiz generation pipeline endpoint."""
    # Setup mocks
    mock_get_path.return_value = "/fake/uploads/video.mp4"
    mock_extract.return_value = "/fake/temp/audio.wav"
    mock_chunk.return_value = ["/fake/temp/audio_chunk_0.mp3"]
    mock_transcribe.return_value = "This is a transcribed educational content."
    mock_summary.return_value = "## Educational Summary\nThis is a summary."
    
    mock_quiz_response = QuizResponse(
        title="Test Educational Quiz",
        questions=[
            QuizQuestion(
                question="What is this test?",
                options=["A test", "B test", "C test", "D test"],
                answer="A test",
                explanation="Pedagogical explanation of test.",
                difficulty="Easy",
                topic="Testing"
            )
        ]
    )
    mock_quiz.return_value = mock_quiz_response
    
    mock_eval_response = QuizEvaluation(
        score=9.5,
        feedback="Excellent quiz structure and clarity."
    )
    mock_evaluate.return_value = mock_eval_response

    # Call generate endpoint
    response = client.post(
        "/generate-quiz",
        json={"video_id": "test-id-123"}
    )
    
    assert response.status_code == 200
    res_data = response.json
    
    # Assert JSON Format matches exactly
    assert res_data["title"] == "Test Educational Quiz"
    assert res_data["summary"] == "## Educational Summary\nThis is a summary."
    assert len(res_data["questions"]) == 1
    assert res_data["questions"][0]["question"] == "What is this test?"
    assert res_data["questions"][0]["difficulty"] == "Easy"
    assert res_data["questions"][0]["topic"] == "Testing"
    assert res_data["evaluation"]["score"] == 9.5
    assert "feedback" in res_data["evaluation"]

    # Verify files were saved to output storage
    quiz_file = Config.OUTPUT_FOLDER / "test-id-123_quiz.json"
    transcript_file = Config.OUTPUT_FOLDER / "test-id-123_transcript.txt"
    assert quiz_file.exists()
    assert transcript_file.exists()

@patch("app.models.quiz_result.QuizResult.query")
def test_get_quiz_endpoints(mock_query, client):
    """Test retrieving and downloading saved quizzes."""
    # Create test data files manually in output directory
    video_id = "mock-quiz-uuid"
    quiz_data = {
        "title": "Mock Quiz",
        "summary": "Mock summary",
        "questions": [],
        "evaluation": {"score": 8.0, "feedback": "Good"}
    }
    
    mock_quiz = MagicMock()
    mock_quiz.id = "mock-quiz-uuid"
    mock_quiz.title = "Mock Quiz"
    mock_quiz.summary = "Mock summary"
    mock_quiz.quiz_json = []
    mock_quiz.evaluation_score = 8.0
    mock_quiz.evaluation_feedback = "Good"
    mock_quiz.transcript = "Mock transcript content"

    def filter_by_side_effect(**kwargs):
        mock_filtered = MagicMock()
        if kwargs.get("id") == "mock-quiz-uuid":
            mock_filtered.first.return_value = mock_quiz
        else:
            mock_filtered.first.return_value = None
        return mock_filtered
    mock_query.filter_by.side_effect = filter_by_side_effect

    # Save mock files
    Config.ensure_directories_exist()
    with open(Config.OUTPUT_FOLDER / f"{video_id}_quiz.json", "w", encoding="utf-8") as f:
        json.dump(quiz_data, f)
    with open(Config.OUTPUT_FOLDER / f"{video_id}_transcript.txt", "w", encoding="utf-8") as f:
        f.write("Mock transcript content")
        
    # 1. Test GET /quiz/<id>
    res_quiz = client.get(f"/quiz/{video_id}")
    assert res_quiz.status_code == 200
    assert res_quiz.json["title"] == "Mock Quiz"
    
    # 2. Test GET /transcript/<id>
    res_tx = client.get(f"/transcript/{video_id}")
    assert res_tx.status_code == 200
    assert res_tx.json["transcript"] == "Mock transcript content"
    
    # 3. Test GET /download/<id>
    res_dl = client.get(f"/download/{video_id}")
    assert res_dl.status_code == 200
    assert "attachment" in res_dl.headers.get("Content-Disposition", "")
    
    # 4. Test Not Found for invalid ID
    res_invalid = client.get("/quiz/non-existent-id")
    assert res_invalid.status_code == 404


@patch("app.services.youtube_service.YouTubeService.download_audio")
@patch("app.services.audio_service.AudioService.chunk_audio")
@patch("app.services.whisper_service.WhisperService.transcribe_chunks")
@patch("app.services.summary_service.SummaryService.generate_summary")
@patch("app.services.quiz_service.QuizService.generate_quiz")
@patch("app.services.evaluation_service.EvaluationService.evaluate_quiz")
def test_generate_youtube_quiz_success(
    mock_evaluate, mock_quiz, mock_summary, mock_transcribe,
    mock_chunk, mock_download, client
):
    """Test successful YouTube quiz generation pipeline."""
    # Setup mocks
    mock_download.return_value = "/fake/temp/youtube.wav"
    mock_chunk.return_value = ["/fake/temp/youtube_chunk_0.mp3"]
    mock_transcribe.return_value = "This is a transcribed educational YouTube video."
    mock_summary.return_value = "## Educational Summary\nThis is a summary of the video."

    mock_quiz_response = QuizResponse(
        title="Test YouTube Quiz",
        questions=[
            QuizQuestion(
                question="What is this test?",
                options=["A test", "B test", "C test", "D test"],
                answer="A test",
                explanation="Pedagogical explanation.",
                difficulty="Easy",
                topic="Testing"
            )
        ]
    )
    mock_quiz.return_value = mock_quiz_response

    mock_eval_response = QuizEvaluation(
        score=9.0,
        feedback="Great structure."
    )
    mock_evaluate.return_value = mock_eval_response

    # Call generate endpoint
    response = client.post(
        "/generate-quiz-from-youtube",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )

    assert response.status_code == 200
    res_data = response.json
    assert res_data["title"] == "Test YouTube Quiz"
    assert res_data["summary"] == "## Educational Summary\nThis is a summary of the video."
    assert len(res_data["questions"]) == 1
    assert res_data["evaluation"]["score"] == 9.0


def test_generate_youtube_quiz_invalid_url(client):
    """Test YouTube endpoint with invalid URL."""
    response = client.post(
        "/generate-quiz-from-youtube",
        json={"youtube_url": "https://example.com/not-youtube"}
    )
    assert response.status_code == 400
    assert "error" in response.json


@patch("app.services.youtube_service.YouTubeService.download_audio")
def test_generate_youtube_quiz_too_long(mock_download, client):
    """Test YouTube endpoint with a video exceeding duration limit."""
    mock_download.side_effect = ValueError("The video duration exceeds the maximum allowed duration")
    response = client.post(
        "/generate-quiz-from-youtube",
        json={"youtube_url": "https://www.youtube.com/watch?v=extremely_long_video"}
    )
    assert response.status_code == 400
    assert "error" in response.json

