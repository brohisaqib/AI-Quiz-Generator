import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from werkzeug.datastructures import FileStorage
from io import BytesIO

from app.services.upload_service import UploadService
from app.services.audio_service import AudioService
from app.services.whisper_service import WhisperService
from app.services.summary_service import SummaryService
from app.services.quiz_service import QuizService
from app.services.evaluation_service import EvaluationService
from app.config.settings import Config
from app.schemas.quiz import QuizResponse, QuizQuestion, QuizEvaluation

# 1. Test UploadService
def test_upload_service_invalid_file():
    service = UploadService()
    # Test empty file storage
    file = FileStorage(stream=BytesIO(), filename="")
    with pytest.raises(ValueError, match="No file uploaded or file is empty"):
        service.handle_upload(file)

@patch("app.services.upload_service.validate_video_upload")
def test_upload_service_success(mock_validate):
    mock_validate.return_value = (True, "")
    service = UploadService()
    
    file_bytes = b"dummy video bytes"
    file = FileStorage(
        stream=BytesIO(file_bytes),
        filename="test.mp4",
        content_type="video/mp4"
    )
    
    res = service.handle_upload(file)
    assert res["filename"] == "test.mp4"
    assert "video_id" in res
    assert Path(res["file_path"]).exists()

# 2. Test AudioService (Mocking moviepy and pydub)
@patch("app.services.audio_service.VideoFileClip")
def test_audio_extraction(mock_video_clip):
    # Mock video clip behavior
    mock_clip_instance = MagicMock()
    mock_clip_instance.audio = MagicMock()
    mock_video_clip.return_value = mock_clip_instance
    
    service = AudioService()
    video_path = "/fake/uploads/video.mp4"
    video_id = "test-uuid-audio"
    
    audio_path = service.extract_audio(video_path, video_id)
    assert "test-uuid-audio_full_audio.wav" in audio_path
    mock_clip_instance.audio.write_audiofile.assert_called_once()
    mock_clip_instance.close.assert_called_once()

@patch("app.services.audio_service.AudioSegment")
def test_audio_chunking(mock_audio_segment):
    # Mock audio track of 5 minutes (300,000ms), which is under chunk limit
    mock_audio = MagicMock()
    mock_audio.__len__.return_value = 300000
    mock_audio_segment.from_file.return_value = mock_audio
    
    service = AudioService()
    chunks = service.chunk_audio("/fake/audio.wav", "test-uuid-chunk")
    
    assert len(chunks) == 1
    assert "test-uuid-chunk_chunk_0.mp3" in chunks[0]
    mock_audio.export.assert_called_once()

# 3. Test WhisperService
@patch("app.services.whisper_service.OpenAI")
def test_whisper_transcription(mock_openai_class):
    # Mock client and transcription response
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    # Mock transcription result object
    mock_response = MagicMock()
    mock_response.strip.return_value = "This is transcription text."
    mock_client.audio.transcriptions.create.return_value = "This is transcription text."
    
    # Set Config API key to non-empty
    Config.OPENAI_API_KEY = "mock-key"
    
    service = WhisperService()
    
    # Mock the file open
    with patch("builtins.open", patch("builtins.open", MagicMock())):
        with patch("os.path.exists", return_value=True):
            text = service.transcribe_chunk("/fake/chunk.mp3")
            assert text == "This is transcription text."

# 4. Test SummaryService
@patch("app.services.summary_service.ChatOpenAI")
def test_summary_service(mock_chat):
    mock_chain_instance = MagicMock()
    mock_chain_instance.invoke.return_value = "Markdown Summary Content."
    
    # Instantiate SummaryService and override chain
    Config.OPENAI_API_KEY = "mock-key"
    service = SummaryService()
    service.chain = mock_chain_instance
    
    summary = service.generate_summary("Some Transcription text.")
    assert summary == "Markdown Summary Content."
    mock_chain_instance.invoke.assert_called_once_with({"transcription": "Some Transcription text."})

# 5. Test QuizService
@patch("app.services.quiz_service.ChatOpenAI")
def test_quiz_service(mock_chat):
    mock_quiz_response = QuizResponse(
        title="Sample Quiz",
        questions=[
            QuizQuestion(
                question="Q?",
                options=["A", "B", "C", "D"],
                answer="A",
                explanation="Exp",
                difficulty="Easy",
                topic="Topic"
            )
        ]
    )
    
    mock_chain_instance = MagicMock()
    mock_chain_instance.invoke.return_value = mock_quiz_response
    
    Config.OPENAI_API_KEY = "mock-key"
    service = QuizService()
    service.chain = mock_chain_instance
    
    quiz = service.generate_quiz("Summary", "Transcription")
    assert quiz.title == "Sample Quiz"
    assert len(quiz.questions) == 1
    mock_chain_instance.invoke.assert_called_once()

# 6. Test EvaluationService
@patch("app.services.evaluation_service.ChatOpenAI")
def test_evaluation_service(mock_chat):
    mock_eval = QuizEvaluation(
        score=9.0,
        feedback="Great job"
    )
    mock_chain_instance = MagicMock()
    mock_chain_instance.invoke.return_value = mock_eval
    
    Config.OPENAI_API_KEY = "mock-key"
    service = EvaluationService()
    service.chain = mock_chain_instance
    
    quiz_obj = QuizResponse(title="Quiz Title", questions=[])
    eval_res = service.evaluate_quiz("Transcript", "Summary", quiz_obj)
    
    assert eval_res.score == 9.0
    assert eval_res.feedback == "Great job"
