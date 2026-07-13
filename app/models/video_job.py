import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.models import db

class VideoJob(db.Model):
    __tablename__ = "video_jobs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=True)
    source_type = db.Column(db.String(50), nullable=False)  # one of "video", "pdf", "topic"
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    # Relationships
    user = db.relationship("User", back_populates="video_jobs")
    quiz_results = db.relationship("QuizResult", back_populates="video_job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VideoJob {self.id}>"
