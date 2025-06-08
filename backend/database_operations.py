import sqlite3
import os
import logging
from typing import Optional, List, Dict, Any, Union # Added Union

# Configure basic logging for the module if it's to be used independently
# Applications using this module might configure logging at a higher level.
# For simplicity here, if no handlers are configured by root logger, add a basic one.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


def _get_db_connection(db_path: str) -> Optional[sqlite3.Connection]:
    """
    Establishes a connection to the SQLite database specified by db_path.
    Ensures the directory for the database exists and enables foreign key constraints.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        Optional[sqlite3.Connection]: A database connection object if successful, otherwise None.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logging.info(f"Created database directory: {db_dir}")

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        logging.debug(f"Database connection established to '{db_path}' with foreign keys ON.")
    except sqlite3.Error as e:
        logging.error(f"Error connecting to database '{db_path}': {e}", exc_info=True)
    return conn


def update_video_record(
    db_path: str,
    original_filepath: str,
    code: Optional[str],
    title: Optional[str],
    publisher: Optional[str],
    duration_seconds: Optional[int],
    standardized_filename: Optional[str],
    actors_list: List[Dict[str, Union[int, str]]] # [{'id': int, 'canonical_name': str}, ...]
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
    conn: Optional[sqlite3.Connection] = None # Define conn here for broader scope

    try:
        conn = _get_db_connection(db_path)
        if not conn:
            # _get_db_connection already logs the error
            return False

        with conn: # Use connection as a context manager for automatic commit/rollback
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO videos (filepath, code, title, publisher, duration_seconds, standardized_filename)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (original_filepath, code, title, publisher, duration_seconds, standardized_filename))
                video_id = cursor.lastrowid
                logging.info(f"Inserted new video record for '{original_filepath}', Video ID: {video_id}")
            except sqlite3.IntegrityError: # Likely UNIQUE constraint on filepath
                logging.info(f"Video record for '{original_filepath}' likely exists. Attempting update.")
                cursor.execute("""
                    UPDATE videos
                    SET code=?, title=?, publisher=?, duration_seconds=?, standardized_filename=?
                    WHERE filepath=?
                """, (code, title, publisher, duration_seconds, standardized_filename, original_filepath))

                # Fetch the video_id after an update
                cursor.execute("SELECT id FROM videos WHERE filepath=?", (original_filepath,))
                video_id_row = cursor.fetchone()
                if video_id_row:
                    video_id = video_id_row[0]
                    logging.info(f"Updated video record for '{original_filepath}', Video ID: {video_id}")

            # Robust video_id check
            if video_id is None:
                # This attempt is if the UPDATE didn't set video_id (because fetchone was None)
                # or if INSERT didn't return lastrowid (very unlikely for successful INSERT)
                logging.warning(f"video_id still None for '{original_filepath}' after initial upsert. Re-querying.")
                cursor.execute("SELECT id FROM videos WHERE filepath=?", (original_filepath,))
                video_id_row = cursor.fetchone()
                if video_id_row:
                    video_id = video_id_row[0]
                    logging.info(f"Re-queried Video ID for '{original_filepath}': {video_id}")
                else:
                    # This is a critical failure.
                    logging.critical(f"CRITICAL: Could not determine Video ID for '{original_filepath}' after all attempts.")
                    raise ValueError(f"Failed to determine video_id for filepath: {original_filepath}")

            # Manage video-actor associations
            logging.debug(f"Deleting existing actor associations for Video ID: {video_id}")
            cursor.execute("DELETE FROM video_actors WHERE video_id=?", (video_id,))

            actors_added_count: int = 0
            if actors_list:
                for actor in actors_list:
                    actor_db_id = actor.get('id')
                    if actor_db_id is not None: # Crucial: only link actors with a valid DB ID
                        try:
                            cursor.execute("INSERT INTO video_actors (video_id, actor_id) VALUES (?, ?)", (video_id, actor_db_id))
                            actors_added_count += 1
                        except sqlite3.IntegrityError as e:
                            logging.warning(f"Could not add association for Video ID {video_id} and Actor ID {actor_db_id}. Error: {e}. Ensure actor ID exists in 'actors' table.")
                    else:
                        logging.warning(f"Actor '{actor.get('canonical_name', 'N/A')}' missing 'id'. Skipping association for Video ID {video_id}.")

            # conn.commit() is called automatically by 'with conn:' on success
            logging.info(f"Successfully processed video '{original_filepath}' (Video ID: {video_id}), linked {actors_added_count} actors.")
            return True

    except sqlite3.Error as e:
        logging.error(f"Database error in update_video_record for '{original_filepath}': {e}", exc_info=True)
        # conn.rollback() is called automatically by 'with conn:' on exception
        return False
    except ValueError as ve: # Catch the specific ValueError raised for missing video_id
        logging.error(str(ve), exc_info=True) # Already logged critically, just re-log here if needed or pass
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred in update_video_record for '{original_filepath}': {e}", exc_info=True)
        return False
    # finally: # Connection is closed by 'with conn:' if it was successfully opened.
    #     if conn:
    #         conn.close()
    #         logging.debug(f"Database connection closed for '{db_path}'.")


if __name__ == '__main__':
    # Configure logging specifically for this test run for clarity
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

    # Add project root to sys.path to allow importing 'database' package
    import sys # ensure sys is imported in this scope
    current_script_dir_main: str = os.path.dirname(os.path.abspath(__file__))
    project_root_dir_main: str = os.path.dirname(current_script_dir_main)
    if project_root_dir_main not in sys.path:
        sys.path.insert(0, project_root_dir_main)

    # Construct path to DB, assuming this script is in backend/
    # This path construction assumes the script is in /app/backend/
    # For robustness, it should ideally be consistent with how other modules find the DB.
    # Using relative paths from this file's location:
    current_script_dir: str = os.path.dirname(os.path.abspath(__file__))
    project_root_dir: str = os.path.dirname(current_script_dir) # up one level to /app
    db_dir_for_test: str = os.path.join(project_root_dir, 'database')
    test_db_path: str = os.path.join(db_dir_for_test, 'video_management_test_db_ops.db') # Use a dedicated test DB

    logging.info(f"--- Testing database_operations.py with DB: {test_db_path} ---")

    # Clean up old test DB if it exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        logging.info(f"Removed old test database: {test_db_path}")

    # Setup: Need to run database_setup.py logic for this new test_db_path
    # For simplicity in this test, we'll assume database_setup.py has created the main DB,
    # and we'll manually create schema here for this specific test DB.
    # Or, better, if database_setup.py can be imported and run against a specific path.
    # For now, let's manually create schema for this test DB.

    conn_setup = _get_db_connection(test_db_path)
    if not conn_setup:
        logging.critical("Could not create connection for test DB setup. Aborting tests.")
        sys.exit(1) # Use sys for exit in __main__

    try:
        from database.database_setup import create_all_tables, insert_sample_data # Assuming it can be imported
        logging.info("Imported setup functions. Creating tables and inserting sample data...")
        if not create_all_tables(conn_setup):
             logging.critical("Failed to create tables for test DB. Aborting.")
             sys.exit(1)
        if not insert_sample_data(conn_setup): # This will insert John Doe (1), Jane Smith (2)
             logging.warning("Sample data insertion for test DB had issues.")
        conn_setup.commit()
        logging.info("Test database schema and sample data created successfully.")
    except ImportError:
        logging.error("Could not import from database_setup.py. Schema might be missing for tests.")
    except Exception as e:
        logging.error(f"Error setting up test DB: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn_setup:
            conn_setup.close()


    # Example 1: New video
    logging.info("\n--- Test 1: New Video ---")
    actors1: List[Dict[str, Union[int, str]]] = [{'id': 1, 'canonical_name': 'John Doe'}]
    success1 = update_video_record(test_db_path,
                            "/path/to/new_video.mp4",
                            "NEW-001", "New Video Title", "New Publisher",
                            120,
                            "[NEW-001] New Video Title - John Doe.mp4",
                            actors1)
    logging.info(f"Test 1 {'' if success1 else 'UN'}SUCCESSFUL")


    # Example 2: Update existing video
    logging.info("\n--- Test 2: Update Video (add Jane Smith) ---")
    actors2: List[Dict[str, Union[int, str]]] = [
        {'id': 1, 'canonical_name': 'John Doe'},
        {'id': 2, 'canonical_name': 'Jane Smith'}
    ]
    success2 = update_video_record(test_db_path,
                            "/path/to/new_video.mp4", # Same filepath to trigger update
                            "NEW-001-UPD", "Updated Title", "Updated Publisher",
                            125,
                            "[NEW-001-UPD] Updated Title - John Doe, Jane Smith.mp4",
                            actors2)
    logging.info(f"Test 2 {'' if success2 else 'UN'}SUCCESSFUL")

    # Example 3: Video with no actors initially, then add one
    logging.info("\n--- Test 3: Video with no actors initially, then add one ---")
    success3a = update_video_record(test_db_path,
                            "/path/to/no_actor_video.avi",
                            "NA-002", "No Actors Here", "Solo Productions",
                            60,
                            "[NA-002] No Actors Here.avi",
                            [])
    logging.info(f"Test 3a (no actors) {'' if success3a else 'UN'}SUCCESSFUL")

    actors3b: List[Dict[str, Union[int, str]]] = [{'id': 2, 'canonical_name': 'Jane Smith'}]
    success3b = update_video_record(test_db_path,
                            "/path/to/no_actor_video.avi", # Same filepath
                            "NA-002", "No Actors Here - Now with Jane!", "Solo Productions",
                            65,
                            "[NA-002] No Actors Here - Now with Jane!.avi",
                            actors3b)
    logging.info(f"Test 3b (add Jane) {'' if success3b else 'UN'}SUCCESSFUL")

    # Example 4: Video with an actor not in DB (should skip association gracefully)
    logging.info("\n--- Test 4: Video with non-DB actor ID ---")
    actors4: List[Dict[str, Union[int, str]]] = [{'id': 999, 'canonical_name': 'Ghost Actor'}]
    success4 = update_video_record(test_db_path,
                            "/path/to/ghost_actor_video.mkv",
                            "GHOST-003", "Ghost in the Machine", "Phantom Films",
                            90,
                            "[GHOST-003] Ghost in the Machine - Ghost Actor.mkv",
                            actors4)
    logging.info(f"Test 4 {'' if success4 else 'UN'}SUCCESSFUL (expected warnings about actor 999).")


    logging.info("\n--- Verifying Data ---")
    try:
        conn_verify = _get_db_connection(test_db_path)
        if conn_verify:
            conn_verify.row_factory = sqlite3.Row # For dict access
            cursor = conn_verify.cursor()
            logging.info("\nVideos table content:")
            for row in cursor.execute("SELECT id, filepath, standardized_filename, title, publisher FROM videos ORDER BY id"):
                logging.info(f"  {dict(row)}")

            logging.info("\nVideo_actors table content:")
            for row in cursor.execute("""
                SELECT va.video_id, v.title as video_title, va.actor_id, a.name as actor_name
                FROM video_actors va
                JOIN videos v ON va.video_id = v.id
                JOIN actors a ON va.actor_id = a.id
                ORDER BY va.video_id, va.actor_id
            """):
                logging.info(f"  {dict(row)}")
            conn_verify.close()
    except Exception as e:
        logging.error(f"Error during verification: {e}", exc_info=True)

    logging.info("--- database_operations.py tests complete ---")
