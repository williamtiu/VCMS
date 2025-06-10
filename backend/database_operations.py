import sqlite3
import os
import logging
from typing import Optional, List, Dict, Any, Union

# Configure module-level logger
logger = logging.getLogger(__name__)
# Note: BasicConfig for the root logger will be set in the __main__ block
# or by the application using this module.
if not logging.getLogger().handlers: # Add a basic handler if no handlers are configured
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )


def _get_db_connection(db_path: str) -> Optional[sqlite3.Connection]:
    """
    Establishes a connection to the SQLite database specified by db_path.
    Ensures the directory for the database exists and enables foreign key constraints.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        Optional[sqlite3.Connection]: A database connection object if successful,
                                       otherwise None.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Ensure dictionary-like row access
        conn.execute("PRAGMA foreign_keys = ON;")
        logger.debug(
            f"Database connection established to '{db_path}' with foreign keys ON."
        )
    except sqlite3.Error as e:
        logger.error(
            f"Error connecting to database '{db_path}': {e}", exc_info=True
        )
    return conn


def update_video_record(
    db_path: str,
    original_filepath: str,
    code: Optional[str],
    title: Optional[str],
    publisher: Optional[str],
    duration_seconds: Optional[int],
    standardized_filename: Optional[str],
    actors_list: List[Dict[str, Union[int, str]]],
) -> bool:
    """
    Inserts a new video record or updates an existing one based on original_filepath.
    Manages actor associations in the `video_actors` table by clearing existing
    associations for the video and adding new ones.

    Args:
        db_path (str): Path to the SQLite database.
        original_filepath (str): The original path of the video file (used as a unique key).
        code (Optional[str]): Video code.
        title (Optional[str]): Video title.
        publisher (Optional[str]): Video publisher.
        duration_seconds (Optional[int]): Duration of the video in seconds.
        standardized_filename (Optional[str]): The generated standardized filename.
        actors_list (List[Dict[str, Union[int, str]]]): A list of actor dictionaries.
            Each dictionary must contain an 'id' key with the actor's database ID
            for creating associations. Example: [{'id': 1, 'canonical_name': 'John Doe'}, ...].

    Returns:
        bool: True if the operation was successful, False otherwise.

    Raises:
        ValueError: If video_id cannot be determined after insert/update attempts.
    """
    video_id: Optional[int] = None
    conn: Optional[sqlite3.Connection] = None

    try:
        conn = _get_db_connection(db_path)
        if not conn:
            return False

        with conn:  # Use connection as a context manager for automatic commit/rollback
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO videos (filepath, code, title, publisher, duration_seconds, standardized_filename)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        original_filepath,
                        code,
                        title,
                        publisher,
                        duration_seconds,
                        standardized_filename,
                    ),
                )
                video_id = cursor.lastrowid
                logger.info(
                    f"Inserted new video record for '{original_filepath}', Video ID: {video_id}"
                )
            except sqlite3.IntegrityError:  # Likely UNIQUE constraint on filepath
                logger.info(
                    f"Video record for '{original_filepath}' likely exists. Attempting update."
                )
                cursor.execute(
                    """
                    UPDATE videos
                    SET code=?, title=?, publisher=?, duration_seconds=?, standardized_filename=?
                    WHERE filepath=?
                    """,
                    (
                        code,
                        title,
                        publisher,
                        duration_seconds,
                        standardized_filename,
                        original_filepath,
                    ),
                )

                cursor.execute(
                    "SELECT id FROM videos WHERE filepath=?", (original_filepath,)
                )
                video_id_row = cursor.fetchone()
                if video_id_row:
                    video_id = video_id_row["id"] # Access by column name
                    logger.info(
                        f"Updated video record for '{original_filepath}', Video ID: {video_id}"
                    )

            if video_id is None:
                logger.warning(
                    f"video_id still None for '{original_filepath}' after initial upsert. Re-querying."
                )
                cursor.execute(
                    "SELECT id FROM videos WHERE filepath=?", (original_filepath,)
                )
                video_id_row = cursor.fetchone()
                if video_id_row:
                    video_id = video_id_row["id"] # Access by column name
                    logger.info(
                        f"Re-queried Video ID for '{original_filepath}': {video_id}"
                    )
                else:
                    logger.critical(
                        f"CRITICAL: Could not determine Video ID for '{original_filepath}' after all attempts."
                    )
                    # Instead of raising ValueError to be caught immediately below,
                    # log and return False directly as per the function's error signaling.
                    return False # Critical error, operation failed

            logger.debug(
                f"Deleting existing actor associations for Video ID: {video_id}"
            )
            cursor.execute("DELETE FROM video_actors WHERE video_id=?", (video_id,))

            actors_added_count: int = 0
            if actors_list:
                valid_actor_links: List[Tuple[Optional[int], Optional[int]]] = []
                for actor in actors_list:
                    actor_db_id = actor.get("id")
                    if actor_db_id is not None:
                        valid_actor_links.append((video_id, actor_db_id))
                    else:
                        logger.warning(
                            f"Actor '{actor.get('canonical_name', 'N/A')}' missing 'id'. "
                            f"Skipping association for Video ID {video_id}."
                        )

                if valid_actor_links:
                    try:
                        cursor.executemany(
                            "INSERT INTO video_actors (video_id, actor_id) VALUES (?, ?)",
                            valid_actor_links,
                        )
                        actors_added_count = len(valid_actor_links)
                    except sqlite3.IntegrityError as e:
                        logger.warning(
                            f"Could not add batch associations for Video ID {video_id}. "
                            f"Ensure actor IDs exist in 'actors' table. " # Error: {e} is implicit with exc_info
                            "Individual problematic links were not inserted.",
                            exc_info=True # Added for better debugging
                        )
                        # If executemany fails, no rows are inserted for that batch.
                        # Depending on desired atomicity, might need row-by-row fallback.
                        # For now, batch failure means actors_added_count remains 0 from this attempt.
                        # If a partial insert is possible and desired, need individual inserts in except.
                        # However, IntegrityError on executemany usually aborts the whole batch.

            logger.info(
                f"Successfully processed video '{original_filepath}' (Video ID: {video_id}), "
                f"attempted to link {len(valid_actor_links) if actors_list and valid_actor_links else 0} valid actors, " # Log attempted links
                f"{actors_added_count} actors linked successfully."
            )
            return True

    except ValueError as ve: # Catch the specific ValueError if it were still raised (now handled by return False)
        logger.error(f"ValueError in update_video_record for '{original_filepath}': {ve}", exc_info=True)
        return False
    except sqlite3.Error as e:
        logger.error(
            f"Database error in update_video_record for '{original_filepath}': {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in update_video_record for '{original_filepath}': {e}",
            exc_info=True,
        )
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s",
        force=True # Ensure this configuration takes precedence for testing
    )
    logger = logging.getLogger(__name__) # Ensure __main__ uses the same logger name as module if desired, or keep as __main__

    import sys

    current_script_dir_main: str = os.path.dirname(os.path.abspath(__file__))
    project_root_dir_main: str = os.path.dirname(current_script_dir_main)
    if project_root_dir_main not in sys.path:
        sys.path.insert(0, project_root_dir_main)

    current_script_dir: str = os.path.dirname(os.path.abspath(__file__))
    project_root_dir: str = os.path.dirname(current_script_dir)
    db_dir_for_test: str = os.path.join(project_root_dir, "database")
    test_db_path: str = os.path.join(
        db_dir_for_test, "video_management_test_db_ops.db"
    )

    logger.info(
        f"--- Testing database_operations.py with DB: {test_db_path} ---"
    )

    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        logger.info(f"Removed old test database: {test_db_path}")

    conn_setup = _get_db_connection(test_db_path)
    if not conn_setup:
        logger.critical(
            "Could not create connection for test DB setup. Aborting tests."
        )
        sys.exit(1)

    try:
        from database.database_setup import create_all_tables, insert_sample_data

        logger.info(
            "Imported setup functions. Creating tables and inserting sample data..."
        )
        if not create_all_tables(conn_setup):
            logger.critical("Failed to create tables for test DB. Aborting.")
            sys.exit(1)
        if not insert_sample_data(conn_setup):
            logger.warning("Sample data insertion for test DB had issues.")
        conn_setup.commit()
        logger.info("Test database schema and sample data created successfully.")
    except ImportError:
        logger.error(
            "Could not import from database_setup.py. Schema might be missing for tests.",
            exc_info=True
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error setting up test DB: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn_setup:
            conn_setup.close()

    logger.info("\n--- Test 1: New Video ---")
    actors1: List[Dict[str, Union[int, str]]] = [
        {"id": 1, "canonical_name": "John Doe"}
    ]
    success1 = update_video_record(
        test_db_path,
        "/path/to/new_video.mp4",
        "NEW-001",
        "New Video Title",
        "New Publisher",
        120,
        "[NEW-001] New Video Title - John Doe.mp4",
        actors1,
    )
    logger.info(f"Test 1 {'' if success1 else 'UN'}SUCCESSFUL")

    logger.info("\n--- Test 2: Update Video (add Jane Smith) ---")
    actors2: List[Dict[str, Union[int, str]]] = [
        {"id": 1, "canonical_name": "John Doe"},
        {"id": 2, "canonical_name": "Jane Smith"},
    ]
    success2 = update_video_record(
        test_db_path,
        "/path/to/new_video.mp4",  # Same filepath to trigger update
        "NEW-001-UPD",
        "Updated Title",
        "Updated Publisher",
        125,
        "[NEW-001-UPD] Updated Title - John Doe, Jane Smith.mp4",
        actors2,
    )
    logger.info(f"Test 2 {'' if success2 else 'UN'}SUCCESSFUL")

    logger.info("\n--- Test 3: Video with no actors initially, then add one ---")
    success3a = update_video_record(
        test_db_path,
        "/path/to/no_actor_video.avi",
        "NA-002",
        "No Actors Here",
        "Solo Productions",
        60,
        "[NA-002] No Actors Here.avi",
        [],
    )
    logger.info(f"Test 3a (no actors) {'' if success3a else 'UN'}SUCCESSFUL")

    actors3b: List[Dict[str, Union[int, str]]] = [
        {"id": 2, "canonical_name": "Jane Smith"}
    ]
    success3b = update_video_record(
        test_db_path,
        "/path/to/no_actor_video.avi",  # Same filepath
        "NA-002",
        "No Actors Here - Now with Jane!",
        "Solo Productions",
        65,
        "[NA-002] No Actors Here - Now with Jane!.avi",
        actors3b,
    )
    logger.info(f"Test 3b (add Jane) {'' if success3b else 'UN'}SUCCESSFUL")

    logger.info("\n--- Test 4: Video with non-DB actor ID ---")
    actors4: List[Dict[str, Union[int, str]]] = [
        {"id": 999, "canonical_name": "Ghost Actor"}
    ]
    success4 = update_video_record(
        test_db_path,
        "/path/to/ghost_actor_video.mkv",
        "GHOST-003",
        "Ghost in the Machine",
        "Phantom Films",
        90,
        "[GHOST-003] Ghost in the Machine - Ghost Actor.mkv",
        actors4,
    )
    logger.info(
        f"Test 4 {'' if success4 else 'UN'}SUCCESSFUL (expected warnings about actor 999)."
    )

    logger.info("\n--- Verifying Data ---")
    try:
        conn_verify = _get_db_connection(test_db_path)
        if conn_verify:
            conn_verify.row_factory = sqlite3.Row  # For dict access
            cursor = conn_verify.cursor()
            logger.info("\nVideos table content:")
            for row in cursor.execute(
                "SELECT id, filepath, standardized_filename, title, publisher FROM videos ORDER BY id"
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
    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)

    logger.info("--- database_operations.py tests complete ---")
