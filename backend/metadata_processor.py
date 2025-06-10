import os
import sys
import json
import shutil
import re
import sqlite3
import subprocess
import logging
from typing import Dict, List, Optional, Any, Tuple, Union

# --- Path setup for direct execution AND for when imported by other modules ---
SCRIPT_DIR_FOR_PATH_MOD = os.path.dirname(
    os.path.abspath(__file__)
)  # backend directory
PROJECT_ROOT_FOR_PATH_MOD = os.path.dirname(
    SCRIPT_DIR_FOR_PATH_MOD
)  # Project root (/app)
if PROJECT_ROOT_FOR_PATH_MOD not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FOR_PATH_MOD)

# Configure module-level logger
logger = logging.getLogger(__name__)
# BasicConfig will be in __main__ for direct execution, or by the app.
if not logger.handlers:  # Add a basic handler if no handlers are configured by app
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )

# Project-specific imports
from backend.filename_parser import parse_filename
from backend.actor_management import (
    get_actor_id_by_name_or_alias,
    get_actor_name_by_id,
    add_actor as backend_add_actor,
)
from ai_models.content_analysis import (
    enhance_textual_metadata,
)  # analyze_transcribed_audio (if used later)
from ai_models.llm_analyzer import (
    configure_ollama_client,
)  # For explicit configuration
from backend.database_operations import update_video_record

# Define default database path relative to project root for use when this module is imported
_SCRIPT_DIR_MODULE = os.path.dirname(os.path.abspath(__file__))  # /app/backend
_PROJECT_ROOT_MODULE = os.path.dirname(_SCRIPT_DIR_MODULE)  # /app
DEFAULT_DB_PATH_MODULE: str = os.path.join(
    _PROJECT_ROOT_MODULE, "database", "video_management.db"
)


def _sanitize_filename_part(part: Any) -> str:
    """
    Sanitizes a part of a filename by removing or replacing unsuitable characters.
    Converts input to string first.

    Args:
        part (Any): The filename part to sanitize.

    Returns:
        str: The sanitized filename part.
    """
    if not part:
        return ""
    sanitized_part = str(part)  # Ensure it's a string
    sanitized_part = re.sub(r"[\\/:*?\"<>|]", "_", sanitized_part)
    sanitized_part = re.sub(r"\s+", " ", sanitized_part).strip()
    return sanitized_part


def generate_standardized_filename(
    consolidated_metadata: Dict[str, Any], original_extension: str
) -> str:
    """
    Constructs a standardized filename string based on consolidated metadata.
    Pattern: "[Code/Publisher] Title - Actor1, Actor2.extension"
    (parts omitted if not available).

    Args:
        consolidated_metadata (Dict[str, Any]): Dictionary containing consolidated data
                                                (code, title, publisher, actors).
        original_extension (str): The original file extension (e.g., ".mp4").

    Returns:
        str: The generated standardized filename string.
    """
    filename_parts: List[str] = []

    code = consolidated_metadata.get("code")
    publisher = consolidated_metadata.get("publisher")
    title = consolidated_metadata.get("title")
    actors = consolidated_metadata.get("actors", [])

    code_publisher_str = ""
    if code:
        code_publisher_str = f"[{_sanitize_filename_part(code)}]"
    elif publisher:
        code_publisher_str = f"[{_sanitize_filename_part(publisher)}]"
    if code_publisher_str:
        filename_parts.append(code_publisher_str)

    if title:
        filename_parts.append(_sanitize_filename_part(title))
    else:
        filename_parts.append("Unknown_Title")

    if actors:
        actor_names = sorted(
            [
                _sanitize_filename_part(actor["canonical_name"])
                for actor in actors
                if isinstance(actor, dict) and actor.get("canonical_name")
            ]
        )
        if actor_names:
            filename_parts.append("- " + ", ".join(actor_names))

    base_name = " ".join(filename_parts).strip()
    base_name = re.sub(r"\s{2,}", " ", base_name).strip()

    if not base_name or (
        base_name == "Unknown_Title" and not code_publisher_str and not actors
    ):
        original_base = os.path.splitext(
            consolidated_metadata.get(
                "original_filename_for_fallback", "Untitled_Video"
            )
        )[0]
        base_name = _sanitize_filename_part(original_base)
        if not base_name:  # Final fallback
            base_name = "Untitled_Video"

    max_len = 200
    if len(base_name) > max_len:
        base_name = base_name[:max_len].strip(" _-.")

    valid_extension = (
        original_extension
        if original_extension and original_extension.startswith(".")
        else ".unknown"
    )
    return f"{base_name}{valid_extension}"


def _prepare_text_for_ai(
    parsed_info: Dict[str, Any],
    current_actors_map: Dict[Union[int, str], Dict[str, Any]],
    original_filename_with_ext: str,
) -> str:
    """
    Prepares a single text string for AI analysis by combining available metadata.

    Args:
        parsed_info (Dict[str, Any]): Data parsed from the filename.
        current_actors_map (Dict[Union[int, str], Dict[str, Any]]): Map of actors
                                                                    derived from filename.
        original_filename_with_ext (str): The original filename with extension.

    Returns:
        str: A combined and cleaned text string for AI input.
    """
    text_for_ai = parsed_info.get("title", "")

    filename_actor_names = [
        data["canonical_name"]
        for data in current_actors_map.values()
        if data.get("source", "").startswith("filename")
        and data.get("canonical_name")
    ]
    if filename_actor_names:
        text_for_ai += " starring " + ", ".join(filename_actor_names)

    text_for_ai = text_for_ai.strip()
    if not text_for_ai:
        text_for_ai = original_filename_with_ext

    text_for_ai = text_for_ai.replace("_", " ").replace(".", " ").replace("-", " ")
    text_for_ai = re.sub(r"\s+", " ", text_for_ai).strip()

    logger.debug(f"Prepared text for AI analysis: '{text_for_ai}'")
    return text_for_ai


def _consolidate_title(
    parsed_title: Optional[str],
    llm_suggested_title: Optional[str],
    fallback_filename_part: str,
) -> str:
    """
    Consolidates title information from filename parsing and LLM suggestion.

    Args:
        parsed_title (Optional[str]): Title from filename parsing.
        llm_suggested_title (Optional[str]): Title suggested by LLM.
        fallback_filename_part (str): A fallback string, usually cleaned original
                                      filename base.

    Returns:
        str: The consolidated title.
    """
    final_title = parsed_title
    if llm_suggested_title:
        is_parsed_title_weak = (
            not final_title
            or len(final_title) < 5
            or "untitled" in final_title.lower()
            or final_title.isdigit()
            or final_title.lower()
            == os.path.splitext(fallback_filename_part)[0]
            .lower()
            .replace("_", " ")
            .replace(".", " ")
        )
        if is_parsed_title_weak:
            final_title = llm_suggested_title
            logger.info(f"Using LLM suggested title: '{final_title}'")
        elif parsed_title:
            logger.info(
                f"Keeping filename-parsed title '{parsed_title}' over LLM suggestion '{llm_suggested_title}'."
            )

    if not final_title:
        final_title = _sanitize_filename_part(
            os.path.splitext(fallback_filename_part)[0]
        )
        if not final_title:
            final_title = "Unknown Title"  # Absolute fallback
        logger.info(f"Using filename as fallback title: '{final_title}'")
    return final_title


def _consolidate_actors(
    current_actors_map: Dict[Union[int, str], Dict[str, Any]],
    llm_identified_actors: Optional[List[str]],
    db_path: str,
) -> List[Dict[str, Any]]:
    """
    Consolidates actor information from filename parsing and LLM.
    Updates current_actors_map with LLM findings.

    Args:
        current_actors_map (Dict[Union[int, str], Dict[str, Any]]):
            Existing map of actors. Keys are actor_id or lowercase actor_name.
            Values are dicts {'id': Optional[int], 'canonical_name': str, 'source': str}.
        llm_identified_actors (Optional[List[str]]): List of actor names from LLM.
        db_path (str): Path to the database.

    Returns:
        List[Dict[str, Any]]: The final list of consolidated actor dictionaries.
    """
    if llm_identified_actors:
        logger.debug(
            f"Consolidating LLM actors: {llm_identified_actors} with existing map: {current_actors_map}"
        )
        for actor_name_llm in llm_identified_actors:
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_llm)
            canonical_name = actor_name_llm
            source_tag = "llm_no_db_match"

            if actor_id:
                name_from_db = get_actor_name_by_id(db_path, actor_id)
                if name_from_db:
                    canonical_name = name_from_db
                source_tag = "llm_db_match"
                if actor_id not in current_actors_map:
                    current_actors_map[actor_id] = {
                        "id": actor_id,
                        "canonical_name": canonical_name,
                        "source": source_tag,
                    }
                else:  # Actor ID already exists, ensure canonical name is from DB
                    current_actors_map[actor_id]["canonical_name"] = canonical_name
            else:  # LLM found an actor not in DB
                if actor_name_llm.lower() not in current_actors_map:
                    current_actors_map[actor_name_llm.lower()] = {
                        "id": None,
                        "canonical_name": canonical_name,
                        "source": source_tag,
                    }

    final_list = [data for data in current_actors_map.values()]
    return final_list


def _consolidate_publisher(
    parsed_publisher: Optional[str], llm_identified_publisher: Optional[str]
) -> Optional[str]:
    """
    Determines the final publisher, prioritizing LLM if available.

    Args:
        parsed_publisher (Optional[str]): Publisher from filename parsing (if any).
        llm_identified_publisher (Optional[str]): Publisher identified by LLM.

    Returns:
        Optional[str]: The consolidated publisher name.
    """
    if llm_identified_publisher:
        logger.info(
            f"Using LLM identified publisher: '{llm_identified_publisher}'"
        )
        return llm_identified_publisher
    if parsed_publisher:  # Fallback to parsed
        logger.info(
            f"Using filename-parsed publisher: '{parsed_publisher}' (rare)"
        )
        return parsed_publisher
    return None


def process_video_file(
    video_filepath: str, db_path: str = DEFAULT_DB_PATH_MODULE
) -> Optional[Dict[str, Any]]:
    """
    Processes a video file: parses filename, optionally runs AI analysis,
    consolidates metadata, generates standardized filename, and updates the database.

    Args:
        video_filepath (str): Absolute or relative path to the video file.
        db_path (str): Path to the SQLite database. Defaults to module's default.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing processing results,
                                  or None if a critical error occurs.
    """
    try:
        logger.info(f"Starting processing for video: {video_filepath}")
        if not os.path.exists(video_filepath):
            logger.error(f"Video file not found: {video_filepath}")
            return None

        original_filename_with_ext: str = os.path.basename(video_filepath)
        original_extension: str = os.path.splitext(original_filename_with_ext)[1]

        parsed_info = parse_filename(original_filename_with_ext)

        actors_map: Dict[Union[int, str], Dict[str, Any]] = {}
        for actor_name_fn in parsed_info.get("actors", []):
            actor_id = get_actor_id_by_name_or_alias(db_path, actor_name_fn)
            canonical_name = actor_name_fn
            if actor_id:
                db_name = get_actor_name_by_id(db_path, actor_id)
                if db_name:
                    canonical_name = db_name
                actors_map[actor_id] = {
                    "id": actor_id,
                    "canonical_name": canonical_name,
                    "source": "filename_db_match",
                }
            else:
                if canonical_name.lower() not in actors_map:
                    actors_map[canonical_name.lower()] = {
                        "id": None,
                        "canonical_name": canonical_name,
                        "source": "filename_no_db_match",
                    }

        has_actors_from_filename = any(
            val.get("id") for val in actors_map.values()
        ) or any(
            val.get("source") == "filename_no_db_match"
            for val in actors_map.values()
        )

        run_content_analysis: bool = not (
            parsed_info.get("title")
            and has_actors_from_filename
            and parsed_info.get("code")
        )
        if run_content_analysis:
            logger.info(
                "Flagged for AI content analysis due to missing/incomplete filename metadata."
            )

        ai_enhancements: Optional[Dict[str, Any]] = None
        if run_content_analysis:
            text_for_ai = _prepare_text_for_ai(
                parsed_info, actors_map, original_filename_with_ext
            )
            ai_enhancements = enhance_textual_metadata(
                text_input=text_for_ai,
                original_filename=original_filename_with_ext,
            )

        raw_ai_results = {
            "text_enhancements": ai_enhancements,
            "audio_analysis": None,
        }

        llm_title = (
            ai_enhancements.get("llm_suggested_title") if ai_enhancements else None
        )
        final_title = _consolidate_title(
            parsed_info.get("title"), llm_title, original_filename_with_ext
        )

        llm_actors = (
            ai_enhancements.get("llm_identified_actors") if ai_enhancements else None
        )
        final_actors_list = _consolidate_actors(actors_map, llm_actors, db_path)

        llm_publisher = (
            ai_enhancements.get("llm_identified_publisher") if ai_enhancements else None
        )
        final_publisher = _consolidate_publisher(None, llm_publisher)

        consolidated_metadata: Dict[str, Any] = {
            "code": parsed_info.get("code"),
            "title": final_title,
            "actors": final_actors_list,
            "publisher": final_publisher,
            "filepath": video_filepath,
            "duration_seconds": None,  # Placeholder
            "standardized_filename": None,  # Generated next
            "original_filename_for_fallback": original_filename_with_ext,
            "ai_llm_suggested_title": llm_title,
            "ai_llm_identified_actors": llm_actors if llm_actors else [],
            "ai_llm_identified_publisher": llm_publisher,
            "ai_network_actor_info": ai_enhancements.get(
                "network_search_actor_results", []
            )
            if ai_enhancements
            else [],
            "ai_network_publisher_info": ai_enhancements.get(
                "network_search_publisher_results", []
            )
            if ai_enhancements
            else [],
        }

        actors_for_db_and_filename = [
            actor for actor in final_actors_list if actor.get("id") is not None
        ]
        temp_meta_for_filename = consolidated_metadata.copy()
        temp_meta_for_filename["actors"] = actors_for_db_and_filename

        consolidated_metadata[
            "standardized_filename"
        ] = generate_standardized_filename(
            temp_meta_for_filename, original_extension
        )
        logger.info(
            f"Generated standardized filename: {consolidated_metadata['standardized_filename']}"
        )

        update_video_record(
            db_path,
            consolidated_metadata["filepath"],
            consolidated_metadata["code"],
            consolidated_metadata["title"],
            consolidated_metadata["publisher"],
            consolidated_metadata["duration_seconds"],
            consolidated_metadata["standardized_filename"],
            actors_for_db_and_filename,
        )

        return {
            "original_filepath": video_filepath,
            "parsed_data_from_filename": parsed_info,
            "content_analysis_triggered": run_content_analysis,
            "raw_content_analysis_results": raw_ai_results,
            "consolidated_metadata": consolidated_metadata,
        }
    except Exception as e:
        logger.error(
            f"Unexpected error in process_video_file for '{video_filepath}': {e}",
            exc_info=True,
        )
        return None


if __name__ == "__main__":
    # sys.path modification is now at the top of the file.

    from database.database_setup import (
        create_connection as setup_create_conn,
        create_all_tables,
        insert_sample_data,
    )

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    logger = logging.getLogger(
        __name__
    )  # Ensure __main__ logger is also named for consistency if needed

    logger.info("--- Main block of metadata_processor.py (Refactored) ---")
    logger.info("Attempting to configure Ollama client for testing...")
    configure_ollama_client()

    test_db_path = os.path.join(
        PROJECT_ROOT_FOR_PATH_MOD, "database", "metadata_processor_test.db"
    )

    if os.path.exists(test_db_path):
        logger.info(f"Deleting existing test database: {test_db_path}")
        os.remove(test_db_path)

    conn_setup = setup_create_conn(test_db_path)
    if conn_setup:
        try:
            logger.info(f"Creating tables in {test_db_path}...")
            if not create_all_tables(conn_setup):
                logger.critical("Failed to create tables for test DB. Aborting.")
                sys.exit(1)
            logger.info(f"Inserting sample data into {test_db_path}...")
            if not insert_sample_data(conn_setup):
                logger.warning("Sample data insertion for test DB had issues.")
            conn_setup.commit()
        except Exception as e_setup:
            logger.error(f"Error setting up test DB: {e_setup}", exc_info=True)
            sys.exit(1)
        finally:
            conn_setup.close()
        logger.info("Test database schema and sample data created successfully.")
    else:
        logger.critical(
            f"Failed to connect to test DB {test_db_path} for setup. Aborting."
        )
        sys.exit(1)

    videos_dir = os.path.join(
        PROJECT_ROOT_FOR_PATH_MOD, "data", "videos_metadata_test_ai_refactored"
    )
    os.makedirs(videos_dir, exist_ok=True)

    dummy_files_info = [
        {
            "name": "[XYZ-789] My Great Movie - John Doe.mp4",
            "content": "movie dummy",
        },
        {"name": "raw_clip_001.avi", "content": "raw dummy"},
        {
            "name": "CookingShow_Ep03_Delicious_Cakes.mkv",
            "content": "cooking dummy",
        },
        {
            "name": "Tech Review The New Phone X.mp4",
            "content": "tech dummy",
        },
        {
            "name": "Performance_UnknownArtist.webm",
            "content": "performance dummy",
        },
    ]

    test_video_paths = []
    for file_info in dummy_files_info:
        filepath = os.path.join(videos_dir, file_info["name"])
        with open(filepath, "w") as f:
            f.write(file_info["content"])
        test_video_paths.append(filepath)

    logger.info(
        f"\n--- Starting Metadata Processor AI Integration Tests (DB: {test_db_path}) ---"
    )
    for video_path in test_video_paths:
        result = process_video_file(video_path, test_db_path)
        if result:
            logger.info(
                f"Full processing result for {video_path}:\n{json.dumps(result, indent=4)}"
            )
        else:
            logger.error(f"Processing failed for {video_path}")
        logger.info("-" * 50)

    logger.info("\n--- Verifying Database Content After AI Processing ---")
    try:
        conn_verify = sqlite3.connect(test_db_path)
        conn_verify.row_factory = sqlite3.Row
        cursor = conn_verify.cursor()

        logger.info("\nVideos table content:")
        for row in cursor.execute(
            "SELECT id, filepath, code, title, publisher, standardized_filename FROM videos ORDER BY id"
        ):
            logger.info(f"  {dict(row)}")

        logger.info("\nVideo_actors table content:")
        for row in cursor.execute(
            """
            SELECT va.video_id, v.title as video_title, va.actor_id, a.name as actor_name
            FROM video_actors va
            JOIN videos v ON va.video_id = v.id
            JOIN actors a ON va.actor_id = a.id
            ORDER BY va.video_id, va.actor_id
        """
        ):
            logger.info(f"  {dict(row)}")

        conn_verify.close()
    except sqlite3.Error as e_verify:
        logger.error(
            f"Error during database verification: {e_verify}", exc_info=True
        )
    finally:
        for path in test_video_paths:
            try:
                os.remove(path)
            except OSError as e_cleanup:
                logger.warning(f"Error removing dummy file {path}: {e_cleanup}")
        if os.path.exists(videos_dir):
            try:
                shutil.rmtree(videos_dir)
                logger.info(f"Cleaned up test directory: {videos_dir}")
            except OSError as e_cleanup_dir:
                logger.warning(
                    f"Error removing test directory {videos_dir}: {e_cleanup_dir}"
                )

    logger.info(
        "\n--- Metadata Processor AI Integration Tests Complete (Refactored) ---"
    )
