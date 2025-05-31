import sys
import os
import json
import sqlite3 # For specific DB error handling
from werkzeug.exceptions import RequestEntityTooLarge

# Adjust sys.path to allow imports from the project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_IMPORTS = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT_FOR_IMPORTS not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FOR_IMPORTS)

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from backend.metadata_processor import process_video_file
from backend.actor_management import (
    add_actor as backend_add_actor,
    add_alias as backend_add_alias,
    get_all_actors_with_aliases
)

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(PROJECT_ROOT_FOR_IMPORTS, 'data', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit for testing
app.secret_key = os.urandom(24)
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT_FOR_IMPORTS, 'database', 'video_management.db')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mkv', 'mov', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', page_title="Page Not Found", active_page="error"), 404

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f"Server Error: {error}") # Good to log the actual error
    flash("An unexpected server error occurred. Please try again later.", "error")
    return render_template('500.html', page_title="Server Error", active_page="error"), 500

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge) # More specific
def request_entity_too_large(error):
    flash(f'File is too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] // 1024 // 1024}MB.', 'error')
    return redirect(url_for('upload_file_route')), 413

# --- Routes ---
@app.route('/')
def home():
    return render_template('home.html', page_title='Home', active_page="home")

@app.route('/upload', methods=['GET', 'POST'])
def upload_file_route():
    if request.method == 'POST':
        if 'video_file' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(request.url)
        file = request.files['video_file']
        if file.filename == '':
            flash('No file selected for upload.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            uploaded_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(uploaded_filepath)
                flash(f'File "{filename}" uploaded successfully. Processing...', 'info')

                db_dir = os.path.dirname(DEFAULT_DB_PATH)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

                print(f"Calling process_video_file with video: {uploaded_filepath}, DB: {DEFAULT_DB_PATH}")
                processing_results = process_video_file(video_filepath=uploaded_filepath, db_path=DEFAULT_DB_PATH)

                if processing_results:
                    flash(f'File "{filename}" processed successfully.', 'success')
                    return render_template('results_display.html',
                                           page_title=f"Results for {filename}",
                                           data=processing_results,
                                           active_page="upload") # Or a dedicated "results" active_page
                else:
                    flash(f'Error processing file "{filename}". Backend processing failed.', 'error')
                    return redirect(url_for('home'))
            except RequestEntityTooLarge as e: # Handle if file.save() itself checks size, though MAX_CONTENT_LENGTH usually stops it earlier
                flash(f'File "{filename}" is too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] // 1024 // 1024}MB.', 'error')
                return redirect(request.url)
            except Exception as e:
                app.logger.error(f"Error saving/processing file '{filename}': {e}")
                flash(f'An unexpected error occurred while saving or processing file: "{filename}".', 'error')
                return redirect(request.url)
        else:
            flash(f'Invalid file type for "{file.filename}". Allowed types are: {", ".join(ALLOWED_EXTENSIONS)}.', 'error')
            return redirect(request.url)

    return render_template('upload_video.html', page_title="Upload Video", active_page="upload")

@app.route('/actors', methods=['GET'])
def manage_actors_route():
    db_dir = os.path.dirname(DEFAULT_DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        flash("Database directory created. Ensure database is initialized if this is the first run.", "info")

    if not os.path.exists(DEFAULT_DB_PATH):
        flash("Database file not found. Please set it up using the CLI: python main.py --setup_db", "warning")
        actors_data = []
    else:
        try:
            actors_data = get_all_actors_with_aliases(DEFAULT_DB_PATH)
            if not actors_data and os.path.getsize(DEFAULT_DB_PATH) > 0: # DB exists, is not empty, but no actors
                 flash("No actors found in the database.", "info")
            elif not actors_data: # DB exists but might be empty or new
                 flash("Database is empty or no actors found. Add some actors!", "info")
        except sqlite3.Error as e:
            app.logger.error(f"Database error in manage_actors_route: {e}")
            flash("A database error occurred while fetching actors. Please try again later.", "error")
            actors_data = []

    return render_template('manage_actors.html',
                           page_title="Manage Actors",
                           actors_list=actors_data,
                           active_page="actors")

@app.route('/actors/add', methods=['POST'])
def add_actor_route():
    actor_name = request.form.get('actor_name')
    if not actor_name:
        flash('Actor name cannot be empty.', 'error')
    else:
        try:
            actor_id = backend_add_actor(DEFAULT_DB_PATH, actor_name)
            # backend_add_actor prints to console. We need more info for flash.
            # For now, assume if ID is returned, it's a success (either added or existed).
            if actor_id is not None:
                 flash(f'Actor "{actor_name}" processed successfully (ID: {actor_id}).', 'success')
            else: # This case might indicate an issue if actor_name was provided.
                 flash(f'Failed to add actor "{actor_name}". See server logs for details.', 'error')
        except sqlite3.Error as e:
            app.logger.error(f"Database error in add_actor_route: {e}")
            flash("A database error occurred while adding the actor.", "error")
        except Exception as e:
            app.logger.error(f"Unexpected error in add_actor_route: {e}")
            flash("An unexpected error occurred.", "error")
    return redirect(url_for('manage_actors_route'))

@app.route('/actors/alias/add', methods=['POST'])
def add_alias_route():
    actor_id_str = request.form.get('actor_id')
    alias_name = request.form.get('alias_name')

    if not actor_id_str or not alias_name:
        flash('Actor ID and Alias Name are required.', 'error')
        return redirect(url_for('manage_actors_route'))

    try:
        actor_id = int(actor_id_str)
        success = backend_add_alias(DEFAULT_DB_PATH, actor_id, alias_name)
        if success:
            flash(f'Alias "{alias_name}" added successfully for actor ID {actor_id}.', 'success')
        else:
            # backend_add_alias prints specific reasons. Flash a more general one, or try to infer.
            flash(f'Failed to add alias "{alias_name}". It may already exist, actor ID could be invalid, or another error occurred.', 'error')
    except ValueError:
        flash('Actor ID must be an integer.', 'error')
    except sqlite3.Error as e:
        app.logger.error(f"Database error in add_alias_route: {e}")
        flash("A database error occurred while adding the alias.", "error")
    except Exception as e:
        app.logger.error(f"Unexpected error in add_alias_route: {e}")
        flash("An unexpected error occurred.", "error")

    return redirect(url_for('manage_actors_route'))

@app.route('/results/file/<filename_param>')
def display_results_route(filename_param):
    # This remains a placeholder for direct linking to results.
    # Actual results are shown immediately after upload POST.
    flash(f"Displaying placeholder results for {filename_param}. DB lookup not yet implemented for this route.", "info")
    mock_data_for_template = { # Keep mock data for this placeholder route
        "original_filepath": os.path.join(app.config['UPLOAD_FOLDER'], filename_param),
        "consolidated_metadata": {"standardized_filename": "N/A (Example)", "title": f"Example Title for {filename_param}", "code": "EX-PLC", "publisher": "Placeholder Publisher", "actors": [{"id":0, "canonical_name":"Placeholder Actor"}]},
        "parsed_data_from_filename": {"code": "EX-PLC", "title":f"Example Title for {filename_param}", "actors":["Placeholder Actor"]},
        "content_analysis_triggered": False, "raw_content_analysis_results": "Not available via this placeholder route."}
    return render_template('results_display.html', page_title=f"Results for {filename_param}", data=mock_data_for_template, active_page="results") # Added active_page

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```
