import pytest
from pathlib import Path
import os
import sys

# Ensure the root folder is in the python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.config.settings import Config

@pytest.fixture
def app():
    """Create a Flask app instance in testing mode."""
    # Use config overrides for testing
    Config.TESTING = True
    
    # Use temporary folders for test run
    test_base = Path(__file__).resolve().parent / "test_data"
    Config.UPLOAD_FOLDER = test_base / "uploads"
    Config.TEMP_FOLDER = test_base / "temp"
    Config.OUTPUT_FOLDER = test_base / "outputs"
    Config.LOG_FOLDER = test_base / "logs"
    Config.ensure_directories_exist()
    
    flask_app = create_app(Config)
    yield flask_app
    
    # Cleanup test directories after tests run
    import shutil
    if test_base.exists():
        shutil.rmtree(test_base)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
