import os
import sys
import json
import shutil
import re
import sqlite3
import subprocess
import logging # Added logging

# Adjust sys.path to ensure project modules can be imported
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Project-specific imports
from backend.filename_parser import parse_filename
from backend.actor_management import get_actor_id_by_name_or_alias, get_actor_name_by_id, add_actor as backend_add_actor # Added add_actor
from ai_models.content_analysis import enhance_textual_metadata, analyze_transcribed_audio # New AI functions
from ai_models.llm_analyzer import configure_ollama_client # To configure Ollama for tests
from backend.database_operations import update_video_record

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')
DEFAULT_DB_PATH = os.path.join(DATABASE_DIR, 'video_management.db')


def sanitize_filename_part(part):
    if not part:
        return ""
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', str(part)) # Ensure part is string
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized

def generate_standardized_filename(consolidated_metadata, original_extension):
    parts = []
    code = consolidated_metadata.get('code')
    publisher = consolidated_metadata.get('publisher')
    title = consolidated_metadata.get('title')
    actors = consolidated_metadata.get('actors')

    code_publisher_part = None
    if code:
        code_publisher_part = f"[{sanitize_filename_part(code)}]"
    elif publisher:
        code_publisher_part = f"[{sanitize_filename_part(publisher)}]"

    if code_publisher_part:
        parts.append(code_publisher_part)

    if title:
        parts.append(sanitize_filename_part(title))
    else:
        parts.append("Unknown_Title")

    if actors:
        actor_names = sorted([sanitize_filename_part(actor['canonical_name']) for actor in actors if actor.get('canonical_name')])
        if actor_names:
             parts.append("- " + ", ".join(actor_names))

    base_name = " ".join(parts).strip()
    if not base_name: # Should be rare if title is always "Unknown_Title"
        base_name = "Untitled_Video"

    # Refined joining logic from previous step
    if len(parts) == 1 and title:
        base_name = parts[0]
    elif code_publisher_part and title and not actors:
        base_name = f"{parts[0]} {parts[1]}"
    elif not code_publisher_part and title and actors:
        base_name = f"{parts[0]} {parts[1]}"
    elif code_publisher_part and title and actors:
         base_name = f"{parts[0]} {parts[1]} {parts[2]}"
    else:
        base_name = " ".join(parts)


    max_len = 200
    if len(base_name) > max_len:
        base_name = base_name[:max_len].strip()

    return f"{base_name}{original_extension if original_extension else '.unknown'}"


def process_video_file(video_filepath, db_path):
    logging.info(f"Processing video: {video_filepath}")
    if not os.path.exists(video_filepath):
        logging.error(f"Video file not found at {video_filepath}")
        return None

    original_filename_with_ext = os.path.basename(video_filepath)
    original_extension = os.path.splitext(original_filename_with_ext)[1]

    # 1. Parse Filename
    parsed_info = parse_filename(original_filename_with_ext)
    logging.info(f"Parsed filename data: {parsed_info}")

    # 2. Actor Lookup (Filename) & Preparation for Consolidation
    # Store as a dictionary for easy merging: key=actor_id (if exists) or name_lowercase
    # Value: {'id': id, 'canonical_name': name, 'source': 'filename'}
    actors_map = {}

    for actor_name_from_fn in parsed_info.get("actors", []):
        actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_from_fn)
        canonical_name = actor_name_from_fn
        if actor_id:
            name_from_db = get_actor_name_by_id(db_path, actor_id)
            if name_from_db: canonical_name = name_from_db
            if actor_id not in actors_map: # Prioritize DB confirmed actors
                 actors_map[actor_id] = {'id': actor_id, 'canonical_name': canonical_name, 'source': 'filename_db_match'}
        else: # Actor not in DB yet
            # Use lowercase name as key for non-DB actors to avoid duplicates like "John Smith" and "john smith"
            # before they get an ID.
            if canonical_name.lower() not in actors_map:
                 actors_map[canonical_name.lower()] = {'id': None, 'canonical_name': canonical_name, 'source': 'filename_no_db_match'}


    # 3. Content Analysis Trigger
    run_content_analysis = False
    # Trigger if essential data is missing or if actors list is empty
    if not parsed_info.get("title") or \
       not parsed_info.get("actors", []) or \
       not parsed_info.get("code"):
        run_content_analysis = True
        logging.info("Flagging for AI content analysis due to missing/incomplete filename metadata.")

    # 4. Content Analysis
    ai_enhancement_results = None
    raw_content_analysis_results = {"text_enhancements": None, "audio_analysis": None}

    if run_content_analysis:
        text_for_ai_analysis = parsed_info.get('title', '')
        # Join existing actor names from filename parsing if available
        temp_actors_for_ai = [data['canonical_name'] for key, data in actors_map.items() if data['source'].startswith('filename')]
        if temp_actors_for_ai:
             text_for_ai_analysis += " starring " + ", ".join(temp_actors_for_ai)

        text_for_ai_analysis = text_for_ai_analysis.strip()
        if not text_for_ai_analysis:
            text_for_ai_analysis = original_filename_with_ext

        text_for_ai_analysis = text_for_ai_analysis.replace('_', ' ').replace('.', ' ').replace('-', ' ')
        logging.info(f"Text for AI analysis: {text_for_ai_analysis}")

        ai_enhancement_results = enhance_textual_metadata(text_input=text_for_ai_analysis, original_filename=original_filename_with_ext)
        raw_content_analysis_results["text_enhancements"] = ai_enhancement_results

        # Placeholder for calling analyze_transcribed_audio if/when transcription is available
        # transcribed_audio = "Simulated transcribed audio with mentions of ActorX and keywords topicA, topicB."
        # if transcribed_audio:
        #    audio_analysis_results = analyze_transcribed_audio(transcribed_audio)
        #    raw_content_analysis_results["audio_analysis"] = audio_analysis_results

    # 5. Consolidate Metadata
    final_title = parsed_info.get("title")
    if ai_enhancement_results and ai_enhancement_results.get("llm_suggested_title"):
        # Prefer LLM title if original is short, generic, or missing
        if not final_title or len(final_title) < 5 or "untitled" in final_title.lower() or final_title.isdigit():
            final_title = ai_enhancement_results["llm_suggested_title"]
            logging.info(f"Using LLM suggested title: {final_title}")
    if not final_title: # Fallback if still no title
         final_title = os.path.splitext(original_filename_with_ext)[0].replace("_", " ").replace(".", " ")
         logging.info(f"Using filename as fallback title: {final_title}")


    if ai_enhancement_results and ai_enhancement_results.get("llm_identified_actors"):
        for actor_name_llm in ai_enhancement_results["llm_identified_actors"]:
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_llm)
            canonical_name = actor_name_llm
            if actor_id:
                name_from_db = get_actor_name_by_id(db_path, actor_id)
                if name_from_db: canonical_name = name_from_db
                if actor_id not in actors_map:
                    actors_map[actor_id] = {'id': actor_id, 'canonical_name': canonical_name, 'source': 'llm_db_match'}
            else: # LLM found an actor not in DB
                # Optionally, auto-add this actor to the DB:
                # actor_id = backend_add_actor(db_path, actor_name_llm)
                # if actor_id and actor_id not in actors_map:
                #    actors_map[actor_id] = {'id': actor_id, 'canonical_name': actor_name_llm, 'source': 'llm_added_to_db'}
                # For now, just record without adding to DB from here:
                if canonical_name.lower() not in actors_map: # Check against existing non-DB actors by name
                    actors_map[canonical_name.lower()] = {'id': None, 'canonical_name': canonical_name, 'source': 'llm_no_db_match'}


    final_publisher = parsed_info.get("publisher") # Not typically parsed from filename by current parser
    if ai_enhancement_results and ai_enhancement_results.get("llm_identified_publisher"):
        # Prefer LLM publisher if found, as filename parser doesn't explicitly get it.
        final_publisher = ai_enhancement_results["llm_identified_publisher"]
        logging.info(f"Using LLM identified publisher: {final_publisher}")


    consolidated_metadata = {
        "code": parsed_info.get("code"),
        "title": final_title,
        "actors": [val for key, val in actors_map.items() if val.get('id') is not None] + \
                  [val for key, val in actors_map.items() if val.get('id') is None], # Put actors with ID first
        "publisher": final_publisher,
        "filepath": video_filepath,
        "duration_seconds": None,
        "standardized_filename": None, # Generated next
        # Storing AI contributions for transparency in the returned data for now
        'ai_llm_suggested_title': ai_enhancement_results.get('llm_suggested_title') if ai_enhancement_results else None,
        'ai_llm_identified_actors': ai_enhancement_results.get('llm_identified_actors') if ai_enhancement_results else None,
        'ai_llm_identified_publisher': ai_enhancement_results.get('llm_identified_publisher') if ai_enhancement_results else None,
        'ai_network_actor_info': ai_enhancement_results.get('network_search_actor_results') if ai_enhancement_results else [],
        'ai_network_publisher_info': ai_enhancement_results.get('network_search_publisher_results') if ai_enhancement_results else [],
    }

    # Filter actors for standardized filename and DB save to only include those with an ID for now
    # or those we decide to auto-add if that logic were enabled.
    # For generate_standardized_filename, it expects canonical_name.
    # For update_video_record, it expects 'id' to be present for linking.
    actors_for_db_and_filename = [actor for actor in consolidated_metadata["actors"] if actor.get("id") is not None]
    # If no actors with ID, but LLM found some, we might want to use their names for filename if not adding to DB.
    # This is a design choice. For now, generate_standardized_filename will use actors_for_db_and_filename.

    temp_consolidated_for_filename_gen = consolidated_metadata.copy()
    temp_consolidated_for_filename_gen['actors'] = actors_for_db_and_filename

    consolidated_metadata["standardized_filename"] = generate_standardized_filename(
        temp_consolidated_for_filename_gen, original_extension
    )
    logging.info(f"Generated standardized filename: {consolidated_metadata['standardized_filename']}")

    update_video_record(
        db_path,
        consolidated_metadata["filepath"],
        consolidated_metadata["code"],
        consolidated_metadata["title"],
        consolidated_metadata["publisher"],
        consolidated_metadata["duration_seconds"],
        consolidated_metadata["standardized_filename"],
        actors_for_db_and_filename # Only pass actors with DB IDs
    )

    return {
        "original_filepath": video_filepath,
        "parsed_data_from_filename": parsed_info,
        # "actors_from_filename_lookup": processed_actors_from_filename, # Replaced by more integrated actors_map logic
        "content_analysis_triggered": run_content_analysis,
        "raw_content_analysis_results": raw_content_analysis_results,
        # "actors_from_content_lookup": processed_actors_from_content, # Replaced by actors_map logic
        "consolidated_metadata": consolidated_metadata
    }


if __name__ == '__main__':
    # Configure Ollama client (important for tests using LLM)
    # This should be called by any app entry point too.
    print("--- Main block of metadata_processor.py ---")
    print("Attempting to configure Ollama client for testing...")
    configure_ollama_client() # From ai_models.llm_analyzer

    db_path = DEFAULT_DB_PATH

    if os.path.exists(db_path):
        logging.info(f"Deleting existing test database: {db_path}")
        os.remove(db_path)

    db_setup_script_path = os.path.join(PROJECT_ROOT, 'database', 'database_setup.py')
    try:
        logging.info(f"Running database setup script: {db_setup_script_path}...")
        subprocess.run(['python', db_setup_script_path], check=True, capture_output=True, text=True)
        logging.info("Database setup script completed successfully for testing.")
    except Exception as e:
        logging.error(f"Error during test DB setup: {e}", exc_info=True)
        sys.exit(1)

    videos_dir = os.path.join(PROJECT_ROOT, "data/videos_metadata_test_ai")
    os.makedirs(videos_dir, exist_ok=True)

    dummy_files_info = [
        {"name": "[XYZ-789] My Great Movie - John Doe.mp4", "content": "dummy"}, # Should not trigger AI much
        {"name": "raw_clip_001.avi", "content": "dummy"}, # Should trigger AI, text is just filename
        {"name": "CookingShow S01E03.mkv", "content": "dummy"}, # AI for title/actors
        {"name": "Tech Review New Gadget.mp4", "content": "dummy"}, # AI for publisher, maybe actors
        {"name": "UnknownPerformanceByStars.webm", "content":"test"} # AI for all
    ]

    test_video_paths = []
    for file_info in dummy_files_info:
        filepath = os.path.join(videos_dir, file_info["name"])
        with open(filepath, "w") as f:
            f.write(file_info["content"])
        test_video_paths.append(filepath)

    logging.info(f"\n--- Starting Metadata Processor AI Integration Tests (DB: {db_path}) ---")
    all_results = []
    for video_path in test_video_paths:
        result = process_video_file(video_path, db_path)
        if result:
            all_results.append(result)
            print(json.dumps(result, indent=4)) # Print full result for better inspection
            print("-" * 40)

    logging.info("\n--- Verifying Database Content After AI Processing ---")
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
        logging.error(f"Error during database verification: {e}", exc_info=True)
    finally:
        for path in test_video_paths:
            try:
                os.remove(path)
            except OSError as e:
                logging.warning(f"Error removing dummy file {path}: {e}")
        if os.path.exists(videos_dir):
            try:
                shutil.rmtree(videos_dir)
                logging.info(f"Cleaned up test directory: {videos_dir}")
            except OSError as e:
                 logging.warning(f"Error removing test directory {videos_dir}: {e}")

    logging.info("\n--- Metadata Processor AI Integration Tests Complete ---")
