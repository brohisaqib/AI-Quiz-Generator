import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.config.settings import Config
from app.utils.logger import get_logger

logger = get_logger("app_factory")

def create_app(config_class=Config) -> Flask:
    """
    Application factory to create and configure the Flask app.
    
    Args:
        config_class: The configuration class to use.
        
    Returns:
        A configured Flask application instance.
    """
    logger.info("Initializing AI Quiz Generator application...")
    
    # 1. Initialize system directories (uploads, temp, outputs, logs, data/)
    config_class.ensure_directories_exist()

    # 2. Validate database config
    config_class.validate_database_config()

    # 3. Validate auth config — log warnings if any values are missing
    config_class.validate_auth_config()
    
    # 4. Instantiate Flask App
    app = Flask(__name__)
    
    # 5. Load configurations
    app.config.from_object(config_class)
    
    # Configure SQLAlchemy Database URI
    app.config["SQLALCHEMY_DATABASE_URI"] = config_class.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Bind database and migrate extensions
    from app.models import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize rate limiter
    from app.api.auth_routes import limiter
    limiter.init_app(app)
    
    # Set Flask's maximum file upload size constraint
    app.config["MAX_CONTENT_LENGTH"] = config_class.MAX_CONTENT_LENGTH

    # 6. Enable CORS
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
    CORS(app, resources={r"/*": {"origins": allowed_origins}})
    logger.info(f"CORS enabled. Allowed origins: {allowed_origins}")

    # 7. Register Blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp)

    from app.api.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
    
    # 8. Global Error Handlers
    @app.errorhandler(413)
    def file_too_large(error):
        max_mb = config_class.MAX_CONTENT_LENGTH / (1024 * 1024)
        logger.warning(f"Global error handler caught 413: Upload size limit exceeded. Max size: {max_mb:.1f}MB")
        return jsonify({
            "success": False,
            "error": f"File is too large. Maximum allowed size is {max_mb:.1f} MB"
        }), 413

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "success": False,
            "error": "The requested resource could not be found."
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Global error handler caught 500: {str(error)}")
        return jsonify({
            "success": False,
            "error": "An internal server error occurred."
        }), 500

    logger.info("Flask application initialized successfully and routes registered.")
    return app
