from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

# Import all models here so that they are registered with SQLAlchemy
# and detected by Flask-Migrate/Alembic.
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.video_job import VideoJob
from app.models.quiz_result import QuizResult
from app.models.password_reset_token import PasswordResetToken

__all__ = ["db", "migrate", "User", "RefreshToken", "VideoJob", "QuizResult", "PasswordResetToken"]
