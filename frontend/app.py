import os
import logging
import sys
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, redirect, request
from dotenv import load_dotenv

# Resolve the absolute path to the root .env relative to this file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configure logging for the frontend
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("frontend")
logger.info(f"Loading .env from: {env_path} (exists={env_path.exists()})")

# Initialize Flask app to serve static frontend
app = Flask(__name__, static_folder="static", static_url_path="")

# Reads from env: "http://backend:5000" in Docker, "http://127.0.0.1:5000" locally
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")
logger.info(f"Configured BACKEND_URL: {BACKEND_URL}")

@app.route("/")
def landing():
    """Serve landing.html as the primary landing page."""
    return send_from_directory(app.static_folder, "landing.html")

@app.route("/app")
def index():
    """Serve index.html for the main app."""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/reset-password")
def reset_password_redirect():
    """Redirect reset password route to main app with token."""
    token = request.args.get("token", "")
    return redirect(f"/app?token={token}")

@app.route("/config")
def get_config():
    """Expose application configuration details to the client-side app."""
    return jsonify({
        "BACKEND_URL": BACKEND_URL
    }), 200

# Catch-all route to redirect all other paths to index.html (supporting SPA client-side routing)
@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    port = int(os.getenv("FRONTEND_PORT", 8501))
    host = os.getenv("FRONTEND_HOST", "0.0.0.0")
    logger.info(f"Starting custom frontend web server on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
