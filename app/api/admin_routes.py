"""Admin routes blueprint.

Defines endpoints for admin management of users and quizzes.
"""

from flask import Blueprint, jsonify
from app.models import db
from app.models.user import User
from app.models.quiz_result import QuizResult
from app.models.video_job import VideoJob
from app.utils.auth import require_admin
from app.utils.logger import get_logger

logger = get_logger("admin_routes")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    """List all users in the system."""
    users = User.query.all()
    user_data = [{
        "id": str(u.id),
        "username": u.username,
        "email": u.email,
        "role": getattr(u, 'role', 'user'),
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None
    } for u in users]
    return jsonify({"success": True, "users": user_data}), 200


@admin_bp.route("/users/<user_id>/deactivate", methods=["PATCH"])
@require_admin
def deactivate_user(user_id):
    """Deactivate a user account."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
    user.is_active = False
    db.session.commit()
    logger.info(f"User {user.username} ({user.id}) deactivated by admin.")
    return jsonify({"success": True, "message": f"User {user.username} deactivated"}), 200


@admin_bp.route("/users/<user_id>/activate", methods=["PATCH"])
@require_admin
def activate_user(user_id):
    """Activate a user account."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
    user.is_active = True
    db.session.commit()
    logger.info(f"User {user.username} ({user.id}) activated by admin.")
    return jsonify({"success": True, "message": f"User {user.username} activated"}), 200


@admin_bp.route("/quizzes", methods=["GET"])
@require_admin
def list_quizzes():
    """List all quizzes from all users."""
    results = (
        db.session.query(QuizResult)
        .outerjoin(VideoJob, QuizResult.video_job_id == VideoJob.id)
        .order_by(QuizResult.created_at.desc())
        .all()
    )
    quiz_data = []
    for row in results:
        source_type = row.video_job.source_type if row.video_job else "unknown"
        question_count = len(row.quiz_json) if isinstance(row.quiz_json, list) else 0
        quiz_data.append({
            "id": str(row.id),
            "title": row.title,
            "source_type": source_type,
            "question_count": question_count,
            "evaluation_score": row.evaluation_score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "username": row.user.username if row.user else "Unknown"
        })
    return jsonify({"success": True, "quizzes": quiz_data}), 200


@admin_bp.route("/stats", methods=["GET"])
@require_admin
def admin_stats():
    """Return platform statistics."""
    total_users = User.query.count()
    total_quizzes = QuizResult.query.count()
    quizzes = QuizResult.query.filter(QuizResult.evaluation_score.isnot(None)).all()
    avg_score = 0
    if quizzes:
        avg_score = sum(q.evaluation_score for q in quizzes) / len(quizzes)
    
    return jsonify({
        "success": True,
        "total_users": total_users,
        "total_quizzes": total_quizzes,
        "average_evaluation_score": round(avg_score, 1)
    }), 200
