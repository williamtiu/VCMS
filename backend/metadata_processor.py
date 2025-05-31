import os
import sys # For path modification
import json # For pretty printing results
import shutil # For creating/removing dummy files if needed
import re # For filename sanitization
import sqlite3 # For test verification
import subprocess # For running DB setup in test

# Adjust sys.path to ensure project modules can be imported
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Project-specific imports
from backend.filename_parser import parse_filename
from backend.actor_management import get_actor_id_by_name_or_alias, get_actor_name_by_id #, add_actor (potential future use)
from ai_models.content_analysis import extract_text_from_video_frames, extract_info_from_audio
from backend.database_operations import update_video_record # New import

# Assuming the database is in the 'database' directory relative to the project root.
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database') # Use PROJECT_ROOT
DEFAULT_DB_PATH = os.path.join(DATABASE_DIR, 'video_management.db')


def sanitize_filename_part(part):
    """Removes or replaces characters not suitable for filenames."""
    if not part:
        return ""
    # Remove characters like / : * ? " < > |
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', part)
    # Replace multiple spaces or underscores with a single one if desired, or just strip
    sanitized = re.sub(r'\s+', ' ', sanitized).strip() # Consolidate multiple spaces to one
    return sanitized

def generate_standardized_filename(consolidated_metadata, original_extension):
    """
    Constructs a standardized filename string based on consolidated metadata.
    Example: [Publisher-Code] Title - Actor1, Actor2.extension
    """
    parts = []

    # Code / Publisher part
    code = consolidated_metadata.get('code')
    publisher = consolidated_metadata.get('publisher')

    code_publisher_part = None
    if code:
        code_publisher_part = f"[{sanitize_filename_part(code)}]"
    elif publisher: # Fallback to publisher if no code
        code_publisher_part = f"[{sanitize_filename_part(publisher)}]" # Or some other format

    if code_publisher_part:
        parts.append(code_publisher_part)

    # Title part
    title = consolidated_metadata.get('title')
    if title:
        parts.append(sanitize_filename_part(title))
    else:
        parts.append("Unknown Title") # Always include a title placeholder

    # Actors part
    actors = consolidated_metadata.get('actors') # List of {'id': ..., 'canonical_name': ...}
    if actors:
        actor_names = sorted([sanitize_filename_part(actor['canonical_name']) for actor in actors])
        if actor_names:
             parts.append("- " + ", ".join(actor_names)) # Prepend with " - " if title exists

    # Join parts
    if not parts: # Should not happen if title is always present
        base_name = "Untitled_Video"
    elif len(parts) == 1 and title: # Only title is present
        base_name = parts[0]
    elif code_publisher_part and title and not actors: # Code/Pub and Title, no actors
        base_name = f"{code_publisher_part} {parts[1]}"
    elif not code_publisher_part and title and actors: # Title and Actors, no code/pub
        base_name = f"{parts[0]} {parts[1]}" # parts[0] is title, parts[1] is " - Actors"
    elif code_publisher_part and title and actors: # All parts
         base_name = f"{code_publisher_part} {parts[1]} {parts[2]}"
    else: # Other combinations or just title if it's the only thing
        base_name = " ".join(parts)


    # Ensure base_name is not excessively long (optional, OS dependent)
    max_len = 200 # Arbitrary max length for the base filename part
    if len(base_name) > max_len:
        base_name = base_name[:max_len].strip()

    return f"{base_name}{original_extension}"


def process_video_file(video_filepath, db_path):
    """
    Processes a video file to extract, analyze, and consolidate metadata.
    Also updates the database with this information.
    """
    print(f"\nProcessing video: {video_filepath}")
    if not os.path.exists(video_filepath):
        print(f"Error: Video file not found at {video_filepath}")
        return None

    original_filename_with_ext = os.path.basename(video_filepath)
    original_extension = os.path.splitext(original_filename_with_ext)[1]

    # 1. Parse Filename
    parsed_filename_data = parse_filename(original_filename_with_ext)

    # 2. Actor Lookup (Filename)
    processed_actors_from_filename = []
    if parsed_filename_data.get("actors"):
        for actor_name_from_fn in parsed_filename_data["actors"]:
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_from_fn)
            processed_actors_from_filename.append({
                'name': actor_name_from_fn,
                'id': actor_id,
                'found_in_db': actor_id is not None
            })

    # 3. Content Analysis Trigger
    run_content_analysis = False
    # Trigger if essential data is missing or if actors list is empty (even if key "actors" exists)
    if not parsed_filename_data.get("title") or \
       not parsed_filename_data.get("actors", []) or \
       not parsed_filename_data.get("code"):
        run_content_analysis = True
        print("Flagging for content analysis due to missing/incomplete filename metadata.")

    # 4. Content Analysis (Placeholder)
    raw_content_analysis_results = {}
    processed_actors_from_content = []
    potential_publisher_ocr = None
    potential_title_ocr = None
    potential_title_audio = None

    if run_content_analysis:
        print("Running content analysis (placeholders)...")
        ocr_results = extract_text_from_video_frames(video_filepath)
        audio_results = extract_info_from_audio(video_filepath)
        raw_content_analysis_results = {"ocr": ocr_results, "audio": audio_results}

        for actor_name_ocr in ocr_results.get("on_screen_actor_names", []):
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_ocr)
            processed_actors_from_content.append({
                'name': actor_name_ocr, 'id': actor_id,
                'source': 'ocr_on_screen', 'found_in_db': actor_id is not None
            })

        for actor_name_audio in audio_results.get("mentioned_actor_names", []):
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_audio)
            processed_actors_from_content.append({
                'name': actor_name_audio, 'id': actor_id,
                'source': 'audio_mentioned', 'found_in_db': actor_id is not None
            })

        potential_publisher_ocr = ocr_results.get("publisher_logo_text")
        for text_item in ocr_results.get("other_text", []):
            if "episode" in text_item.lower() or "title" in text_item.lower() or \
               (len(text_item.split()) > 2 and any(w.istitle() for w in text_item.split())): # Crude title check
                potential_title_ocr = text_item
                break
        if audio_results.get("mentioned_title_keywords"):
            potential_title_audio = " ".join(audio_results["mentioned_title_keywords"])

    # 5. Consolidate Metadata
    consolidated_metadata = {
        "code": parsed_filename_data.get("code"),
        "title": parsed_filename_data.get("title"),
        "actors": [],
        "publisher": None,
        "filepath": video_filepath, # Original filepath
        "duration_seconds": None, # Placeholder, can be filled by a media info tool
        "standardized_filename": None # Will be filled next
    }

    if not consolidated_metadata["title"]:
        title_options = [potential_title_ocr, potential_title_audio,
                         os.path.splitext(original_filename_with_ext)[0].replace("_", " ").replace(".", " ")]
        consolidated_metadata["title"] = next((t for t in title_options if t), "Untitled Video")
        print(f"Used title from {'OCR' if consolidated_metadata['title'] == potential_title_ocr else 'Audio' if consolidated_metadata['title'] == potential_title_audio else 'filename'}: {consolidated_metadata['title']}")

    if potential_publisher_ocr:
        consolidated_metadata["publisher"] = potential_publisher_ocr
        print(f"Used publisher from OCR: {potential_publisher_ocr}")

    final_actor_map = {}
    all_processed_actors = processed_actors_from_filename + processed_actors_from_content
    for actor_info in all_processed_actors:
        actor_id = actor_info['id']
        if actor_id is not None:
            if actor_id not in final_actor_map:
                canonical_name = get_actor_name_by_id(db_path, actor_id)
                if canonical_name:
                    final_actor_map[actor_id] = {"id": actor_id, "canonical_name": canonical_name}
    consolidated_metadata["actors"] = list(final_actor_map.values())

    # Generate Standardized Filename
    consolidated_metadata["standardized_filename"] = generate_standardized_filename(
        consolidated_metadata, original_extension
    )
    print(f"Generated standardized filename: {consolidated_metadata['standardized_filename']}")

    # Database Update
    update_video_record(
        db_path,
        consolidated_metadata["filepath"],
        consolidated_metadata["code"],
        consolidated_metadata["title"],
        consolidated_metadata["publisher"],
        consolidated_metadata["duration_seconds"], # Will be None for now
        consolidated_metadata["standardized_filename"],
        consolidated_metadata["actors"]
    )

    # Prepare return data (as before, but consolidated_metadata now includes standardized_filename)
    return {
        "original_filepath": video_filepath,
        "parsed_data_from_filename": parsed_filename_data,
        "actors_from_filename_lookup": processed_actors_from_filename,
        "content_analysis_triggered": run_content_analysis,
        "raw_content_analysis_results": raw_content_analysis_results if run_content_analysis else "Not Performed",
        "actors_from_content_lookup": processed_actors_from_content if run_content_analysis else [],
        "consolidated_metadata": consolidated_metadata
    }


if __name__ == '__main__':
    db_path = DEFAULT_DB_PATH

    # Ensure database is set up (run database_setup.py manually or via CLI if needed)
    # For this test, we assume it's been run once.
    # To ensure a clean slate for testing this specifically:
    if os.path.exists(db_path):
        print(f"Deleting existing test database: {db_path}")
        os.remove(db_path)

    # Run setup (using subprocess as in main.py example)
    db_setup_script_path = os.path.join(PROJECT_ROOT, 'database', 'database_setup.py')
    try:
        print(f"Running database setup script: {db_setup_script_path}...")
        subprocess.run(['python', db_setup_script_path], check=True, capture_output=True, text=True)
        print("Database setup script completed successfully for testing.")
    except Exception as e:
        print(f"Error during test DB setup: {e}")
        sys.exit(1) # Stop if DB setup fails

    videos_dir = os.path.join(PROJECT_ROOT, "data/videos_metadata_test")
    os.makedirs(videos_dir, exist_ok=True)

    dummy_files_info = [
        {"name": "[XYZ-789] My Great Movie - John Doe.mp4", "content": "dummy"},
        {"name": "raw_clip_001_StudioX.avi", "content": "dummy"},
        {"name": "Another Publisher Action Film - Jane Smith & John Doe.mkv", "content": "dummy"},
        {"name": "Unknown Performance.mp4", "content": "dummy"},
        {"name": "JustATitle.webm", "content":"test"} # Test no actors, no code
    ]

    test_video_paths = []
    for file_info in dummy_files_info:
        filepath = os.path.join(videos_dir, file_info["name"])
        with open(filepath, "w") as f:
            f.write(file_info["content"])
        test_video_paths.append(filepath)

    print(f"\n--- Starting Metadata Processor Tests (DB: {db_path}) ---")
    all_results = []
    for video_path in test_video_paths:
        result = process_video_file(video_path, db_path)
        if result:
            all_results.append(result)
            print(json.dumps(result['consolidated_metadata'], indent=4))
            print("-" * 40)

    print("\n--- Verifying Database Content ---")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\nVideos table:")
        for row in cursor.execute("SELECT id, filepath, code, title, publisher, standardized_filename FROM videos ORDER BY id"):
            print(dict(row))

        print("\nVideo_actors table:")
        for row in cursor.execute("SELECT va.video_id, v.title as video_title, va.actor_id, a.name as actor_name FROM video_actors va JOIN videos v ON va.video_id = v.id JOIN actors a ON va.actor_id = a.id ORDER BY va.video_id, va.actor_id"):
            print(dict(row))

        conn.close()
    except sqlite3.Error as e:
        print(f"Error during database verification: {e}")
    finally:
        # Clean up dummy files and directory
        for path in test_video_paths:
            try:
                os.remove(path)
            except OSError as e:
                print(f"Error removing dummy file {path}: {e}")
        if os.path.exists(videos_dir):
            try:
                shutil.rmtree(videos_dir)
                print(f"Cleaned up test directory: {videos_dir}")
            except OSError as e:
                 print(f"Error removing test directory {videos_dir}: {e}")

    print("\n--- Metadata Processor Tests Complete ---")
