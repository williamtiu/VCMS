import os
import logging  # Moved to top

# Determine Project Root - assumes config.py is in webapp/
# So, os.path.dirname(__file__) is webapp/
# os.path.dirname(os.path.dirname(__file__)) is project root /app
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    """Flask configuration variables."""

    # Application settings
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24)
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    # Upload settings
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "data", "uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB limit
    ALLOWED_EXTENSIONS = {"mp4", "avi", "mkv", "mov", "webm"}

    # Database settings
    DEFAULT_DB_PATH = os.path.join(
        PROJECT_ROOT, "database", "video_management.db"
    )

    # AI Model settings (can be expanded)
    # OLLAMA_HOST = os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    # OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL") or "llama3"

    # Logging
    LOG_LEVEL = (
        logging.DEBUG
        if os.environ.get("FLASK_DEBUG", "False").lower() == "true"
        else logging.INFO
    )


# Example of how to ensure UPLOAD_FOLDER exists when config is loaded,
# though app.py also does this.
# if not os.path.exists(Config.UPLOAD_FOLDER):
#     os.makedirs(Config.UPLOAD_FOLDER)
# print(f"Config: UPLOAD_FOLDER set to {Config.UPLOAD_FOLDER}")
# print(f"Config: DEFAULT_DB_PATH set to {Config.DEFAULT_DB_PATH}")
# print(f"Config: Project Root determined as {PROJECT_ROOT}")
```
