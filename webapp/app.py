import sys
import os
import json
import sqlite3  # For specific DB error handling in routes
import logging  # For app.logger.setLevel
from typing import Dict, List, Optional, Any, Tuple

# --- Path setup for direct execution AND for when imported by other modules ---
# This allows the script to be run directly for testing, resolving imports for
# sibling modules, and ensures that when imported, "webapp" is correctly
# identified as a package if the project root is in sys.path.
SCRIPT_DIR_APP = os.path.dirname(os.path.abspath(__file__))  # webapp directory
PROJECT_ROOT_APP = os.path.dirname(SCRIPT_DIR_APP)  # Project root (/app)
if PROJECT_ROOT_APP not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_APP)

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Import configuration
from webapp.config import Config

# Import backend and AI modules
from backend.metadata_processor import process_video_file
from backend.actor_management import (
    add_actor as backend_add_actor,
    add_alias as backend_add_alias,
    get_all_actors_with_aliases,
)
from ai_models.llm_analyzer import (
    configure_ollama_client,
    DEFAULT_OLLAMA_HOST as LLM_DEFAULT_HOST,
)

# --- Application Setup ---
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])
    # app.logger is available after app = Flask(__name__)
    app.logger.info(f"Created upload folder: {app.config['UPLOAD_FOLDER']}")


# Configure logging level for Flask app logger
if app.config.get("DEBUG"):  # app.debug is set by app.config.from_object(Config)
    app.logger.setLevel(logging.DEBUG)
else:
    app.logger.setLevel(logging.INFO)
app.logger.info(
    f"Flask app logger initialized with level: {logging.getLevelName(app.logger.getEffectiveLevel())}"
)


# Initialize Ollama Client at application startup
ollama_host_to_configure = app.config.get("OLLAMA_HOST", LLM_DEFAULT_HOST)
app.logger.info(
    f"Attempting to configure Ollama client with host: {ollama_host_to_configure} at app startup."
)
if configure_ollama_client(ollama_host_to_configure):
    app.logger.info("Ollama client configured successfully via app startup.")
else:
    app.logger.warning(
        "Ollama client could not be configured at app startup. AI features may be limited."
    )


# --- Helper Functions ---
def allowed_file(filename: str) -> bool:
    """Checks if the uploaded file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(error: Exception) -> Tuple[str, int]:
    """Handles 404 errors by rendering a custom page."""
    app.logger.warning(f"404 error encountered: {error}", exc_info=True)
    return (
        render_template("404.html", page_title="Page Not Found", active_page="error"),
        404,
    )


@app.errorhandler(500)
def internal_server_error(error: Exception) -> Tuple[str, int]:
    """Handles 500 internal server errors by rendering a custom page."""
    app.logger.error(f"Server Error 500: {error}", exc_info=True)
    return (
        render_template("500.html", page_title="Server Error", active_page="error"),
        500,
    )


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def request_entity_too_large(error: Exception) -> Tuple[Any, int]:
    """Handles 413 Request Entity Too Large errors (file uploads too big)."""
    max_size_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // 1024 // 1024
    flash(f"File is too large. Maximum size is {max_size_mb}MB.", "error")
    app.logger.warning(f"File upload rejected (too large): {error}", exc_info=True)
    return redirect(url_for("upload_file_route")), 413


# --- Routes ---
@app.route("/")
def home() -> str:
    """Renders the home page."""
    return render_template("home.html", page_title="Home", active_page="home")


@app.route("/upload", methods=["GET", "POST"])
def upload_file_route() -> Any:
    """Handles video file uploads and initiates backend processing."""
    if request.method == "POST":
        if "video_file" not in request.files:
            flash("No file part in the request.", "error")
            return redirect(request.url)

        file = request.files["video_file"]

        if not file or not file.filename: # Check if file object exists and has a filename
            flash("No file selected for upload.", "error")
            return redirect(request.url)

        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            uploaded_filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            try:
                file.save(uploaded_filepath)
                app.logger.info(
                    f"File '{filename}' uploaded successfully to '{uploaded_filepath}'. "
                    "Initiating processing..."
                )
                flash(f"File '{filename}' uploaded. Processing...", "info")

                db_path_for_processing = app.config["DEFAULT_DB_PATH"]

                db_dir = os.path.dirname(db_path_for_processing)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    app.logger.info(
                        f"Created database directory for processing: {db_dir}"
                    )

                app.logger.info(
                    f"Calling process_video_file for video: {uploaded_filepath}, DB: {db_path_for_processing}"
                )
                processing_results = process_video_file(
                    video_filepath=uploaded_filepath, db_path=db_path_for_processing
                )

                if processing_results:
                    flash(f"File '{filename}' processed successfully.", "success")
                    return render_template(
                        "results_display.html",
                        page_title=f"Results for {filename}",
                        data=processing_results,
                        active_page="results",
                    )
                else:
                    flash(
                        f"Error processing file '{filename}'. Backend processing may have failed. Check server logs.",
                        "error",
                    )
                    return redirect(url_for("home"))

            except RequestEntityTooLarge:
                max_size_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // 1024 // 1024
                flash(
                    f"File '{filename}' is too large. Maximum size is {max_size_mb}MB.",
                    "error",
                )
                app.logger.warning(f"File upload rejected (too large): {filename}")
                return redirect(request.url)
            except Exception as e:
                app.logger.error(
                    f"Error saving or processing file '{filename}': {e}",
                    exc_info=True,
                )
                flash(
                    f"An unexpected error occurred while saving or processing file: '{filename}'.",
                    "error",
                )
                return redirect(request.url)
        else:
            flash(
                f"Invalid file type for '{file.filename}'. "
                f"Allowed types are: {', '.join(app.config['ALLOWED_EXTENSIONS'])}.",
                "error",
            )
            return redirect(request.url)

    return render_template(
        "upload_video.html", page_title="Upload Video", active_page="upload"
    )


@app.route("/actors", methods=["GET"])
def manage_actors_route() -> str:
    """Displays the actor management page with a list of actors and their aliases."""
    db_path = app.config["DEFAULT_DB_PATH"]
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir): # Ensure directory for DB exists
        os.makedirs(db_dir, exist_ok=True)
        app.logger.info(f"Created database directory: {db_dir}")

    actors_data: List[Dict[str, Any]] = []
    if not os.path.exists(db_path):
        flash(
            "Database file not found. Please set it up using the CLI: `python main.py --setup_db`",
            "warning",
        )
    else:
        try:
            actors_data = get_all_actors_with_aliases(db_path)
            if not actors_data and os.path.getsize(db_path) > 0:
                flash(
                    "No actors found in the database. Add some using the form below.",
                    "info",
                )
            elif not actors_data: # DB might be empty or new
                flash(
                    "Database appears empty or no actors found. Add some actors!", "info"
                )
        except sqlite3.Error as e:
            app.logger.error(
                f"Database error in manage_actors_route: {e}", exc_info=True
            )
            flash(
                "A database error occurred while fetching actors. Please try again later.",
                "error",
            )
            # actors_data remains []

    return render_template(
        "manage_actors.html",
        page_title="Manage Actors",
        actors_list=actors_data,
        active_page="actors",
    )


@app.route("/actors/add", methods=["POST"])
def add_actor_route() -> Any:  # Returns Response (redirect)
    """Handles form submission for adding a new actor."""
    actor_name: Optional[str] = request.form.get("actor_name")
    db_path: str = app.config["DEFAULT_DB_PATH"]

    if not actor_name or not actor_name.strip():
        flash("Actor name cannot be empty.", "error")
    else:
        try:
            actor_id = backend_add_actor(db_path, actor_name.strip())
            if actor_id is not None:
                flash(
                    f"Actor '{actor_name.strip()}' processed successfully (ID: {actor_id}).",
                    "success",
                )
            else:
                flash(
                    f"Failed to add or find actor '{actor_name.strip()}'. "
                    "Database error or actor name might be invalid.", # More specific
                    "error",
                )
        except sqlite3.Error as e:
            app.logger.error(
                f"Database error in add_actor_route for '{actor_name}': {e}",
                exc_info=True,
            )
            flash("A database error occurred while adding the actor.", "error")
        except Exception as e:
            app.logger.error(
                f"Unexpected error in add_actor_route for '{actor_name}': {e}",
                exc_info=True,
            )
            flash("An unexpected error occurred while adding the actor.", "error")
    return redirect(url_for("manage_actors_route"))


@app.route("/actors/alias/add", methods=["POST"])
def add_alias_route() -> Any:  # Returns Response (redirect)
    """Handles form submission for adding an alias to an actor."""
    actor_id_str: Optional[str] = request.form.get("actor_id")
    alias_name: Optional[str] = request.form.get("alias_name")
    db_path: str = app.config["DEFAULT_DB_PATH"]

    if not actor_id_str or not alias_name or not alias_name.strip():
        flash("Actor ID and a non-empty Alias Name are required.", "error")
        return redirect(url_for("manage_actors_route"))

    try:
        actor_id: int = int(actor_id_str)
        success: bool = backend_add_alias(db_path, actor_id, alias_name.strip())
        if success:
            flash(
                f"Alias '{alias_name.strip()}' added successfully for actor ID {actor_id}.",
                "success",
            )
        else:
            flash(
                f"Failed to add alias '{alias_name.strip()}'. Possible reasons: "
                "Actor ID invalid, alias already in use globally, or it already exists for this actor.",
                "error",
            )
    except ValueError:
        flash("Actor ID must be an integer.", "error")
    except sqlite3.Error as e:
        app.logger.error(
            f"Database error in add_alias_route for alias '{alias_name}': {e}",
            exc_info=True,
        )
        flash("A database error occurred while adding the alias.", "error")
    except Exception as e:
        app.logger.error(
            f"Unexpected error in add_alias_route for alias '{alias_name}': {e}",
            exc_info=True,
        )
        flash("An unexpected error occurred while adding the alias.", "error")

    return redirect(url_for("manage_actors_route"))


@app.route("/results/file/<filename_param>")
def display_results_route(filename_param: str) -> str:
    """
    Placeholder route to display results for a given filename.
    (Currently serves mock data as direct linking to results post-upload is not fully implemented).
    """
    app.logger.info(
        f"Placeholder display_results_route accessed for filename: {filename_param}"
    )
    flash(
        f"Displaying placeholder results for {filename_param}. This route is for demonstration.",
        "info",
    )
    mock_data_for_template: Dict[str, Any] = {
        "original_filepath": os.path.join(
            app.config["UPLOAD_FOLDER"], filename_param
        ),
        "consolidated_metadata": {
            "standardized_filename": "N/A (Example from placeholder route)",
            "title": f"Example Title for {filename_param}",
            "code": "EX-PLC",
            "publisher": "Placeholder Publisher",
            "actors": [
                {
                    "id": 0,
                    "canonical_name": "Placeholder Actor",
                    "source": "placeholder",
                }
            ],
        },
        "parsed_data_from_filename": {
            "code": "EX-PLC",
            "title": f"Example Title for {filename_param}",
            "actors": ["Placeholder Actor"],
        },
        "content_analysis_triggered": False,
        "raw_content_analysis_results": {
            "text_enhancements": "Not available via this placeholder route.",
            "audio_analysis": None,
        },
    }
    return render_template(
        "results_display.html",
        page_title=f"Results for {filename_param}",
        data=mock_data_for_template,
        active_page="results",
    )


if __name__ == "__main__":
    # sys.path manipulation is at the top of the file now.
    app.run(debug=app.config.get("DEBUG", True), host="0.0.0.0", port=5000)
```
