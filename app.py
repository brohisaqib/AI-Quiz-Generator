import os
from app import create_app
from app.utils.logger import get_logger

logger = get_logger("entrypoint")

app = create_app()

if __name__ == "__main__":
    # Get port and host configurations
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    # In production (Docker/Gunicorn), this file is not used.
    # Debug/reload are driven by FLASK_ENV for local dev only.
    debug = os.getenv("FLASK_ENV", "production") == "development"
    
    logger.info(f"Starting server on {host}:{port} (debug={debug})")
    
    # Run the application — debug and reloader are controlled by FLASK_ENV
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
