import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.models import db

class QuizResult(db.Model):
    __tablename__ = "quiz_results"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_job_id = db.Column(UUID(as_uuid=True), db.ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    quiz_json = db.Column(db.JSON, nullable=False)
    evaluation_score = db.Column(db.Float, nullable=True)
    evaluation_feedback = db.Column(db.Text, nullable=True)
    transcript = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(50), nullable=True, default="Intermediate")
    time_limit_minutes = db.Column(db.Integer, nullable=True, default=None)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    # Relationships
    user = db.relationship("User", back_populates="quiz_results")
    video_job = db.relationship("VideoJob", back_populates="quiz_results")

    def __repr__(self) -> str:
        return f"<QuizResult {self.id}>"
