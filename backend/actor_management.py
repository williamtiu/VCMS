import sqlite3
import os
import logging
from typing import Optional, List, Dict, Union, Tuple

# Configure logging for the module
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# Define database path for default use (e.g., by other modules)
_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.dirname(_SCRIPT_DIR)
DEFAULT_DB_PATH_MODULE: str = os.path.join(_PROJECT_ROOT, 'database', 'video_management.db')

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
            logger.info(f"Created database directory: {db_dir}")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        logger.debug(f"Database connection established to '{db_path}' with foreign keys ON.")
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database '{db_path}': {e}", exc_info=True)
    return conn

def add_actor(db_path: str, actor_name: str) -> Optional[int]:
    """
    Adds a new actor to the actors table.
    If the actor already exists, returns the existing actor's ID.

    Args:
        db_path (str): Path to the SQLite database.
        actor_name (str): The name of the actor to add.

    Returns:
        Optional[int]: The ID of the newly added or existing actor, or None if an error occurs
                       or actor_name is empty.
    """
    if not actor_name or not actor_name.strip():
        logger.warning("Attempted to add an actor with an empty name.")
        return None
    normalized_name_for_check = actor_name.strip()

    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return None
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM actors WHERE name = ?", (normalized_name_for_check,))
            row = cursor.fetchone()
            if row:
                logger.info(f"Actor '{normalized_name_for_check}' already exists with ID: {row['id']}.")
                return row['id']

            cursor.execute("INSERT INTO actors (name) VALUES (?)", (normalized_name_for_check,))
            new_actor_id = cursor.lastrowid
            logger.info(f"Actor '{normalized_name_for_check}' added with ID: {new_actor_id}.")
            return new_actor_id
    except sqlite3.IntegrityError as e:
        logger.warning(f"Integrity error adding actor '{normalized_name_for_check}': {e}. Attempting to retrieve existing ID.", exc_info=True)
        try:
            with _get_db_connection(db_path) as conn_retry:
                 if not conn_retry: return None
                 cursor_retry = conn_retry.cursor()
                 cursor_retry.execute("SELECT id FROM actors WHERE name = ?", (normalized_name_for_check,))
                 row_retry = cursor_retry.fetchone()
                 if row_retry:
                     logger.info(f"Found existing actor '{normalized_name_for_check}' with ID {row_retry['id']} after integrity error.")
                     return row_retry['id']
        except sqlite3.Error as e_retry:
            logger.error(f"Error during retry-fetch for actor '{normalized_name_for_check}': {e_retry}", exc_info=True)
        return None
    except sqlite3.Error as e:
        logger.error(f"Database error while adding actor '{normalized_name_for_check}': {e}", exc_info=True)
        return None

def add_alias(db_path: str, actor_id: int, alias_name: str) -> bool:
    """
    Adds a new alias for the given actor_id.

    Args:
        db_path (str): Path to the SQLite database.
        actor_id (int): The ID of the actor.
        alias_name (str): The alias name to add.

    Returns:
        bool: True if alias was added successfully, False otherwise.
    """
    if not alias_name or not alias_name.strip():
        logger.warning("Attempted to add an empty alias name.")
        return False
    if actor_id is None:
        logger.warning("Attempted to add an alias with None actor_id.")
        return False
    normalized_alias_name = alias_name.strip()

    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return False
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM actors WHERE id = ?", (actor_id,))
            if not cursor.fetchone():
                logger.warning(f"Attempted to add alias for non-existent actor ID: {actor_id}.")
                return False
            cursor.execute("SELECT actor_id FROM actor_aliases WHERE alias_name = ?", (normalized_alias_name,))
            row = cursor.fetchone()
            if row:
                if row['actor_id'] == actor_id:
                    logger.info(f"Alias '{normalized_alias_name}' already exists for actor ID {actor_id}.")
                else:
                    logger.warning(f"Alias '{normalized_alias_name}' already exists for a different actor (ID: {row['actor_id']}). Cannot add.")
                return False

            cursor.execute("INSERT INTO actor_aliases (actor_id, alias_name) VALUES (?, ?)", (actor_id, normalized_alias_name))
            logger.info(f"Alias '{normalized_alias_name}' added for actor ID {actor_id}.")
            return True
    except sqlite3.IntegrityError as e:
        logger.warning(f"Integrity error adding alias '{normalized_alias_name}' for actor ID {actor_id}: {e}.", exc_info=True)
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error while adding alias '{normalized_alias_name}' for actor ID {actor_id}: {e}", exc_info=True)
        return False

def get_actor_id_by_name_or_alias(db_path: str, name: str) -> Optional[int]:
    """
    Searches for a given name in actors and actor_aliases tables.

    Args:
        db_path (str): Path to the SQLite database.
        name (str): The name or alias to search for.

    Returns:
        Optional[int]: Actor_id if found, else None.
    """
    if not name or not name.strip():
        logger.debug("Attempted to search for an empty name or alias.")
        return None
    normalized_name = name.strip()
    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return None
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM actors WHERE name = ?", (normalized_name,))
            row = cursor.fetchone()
            if row:
                logger.debug(f"Found actor ID {row['id']} by direct name match for '{normalized_name}'.")
                return row['id']
            cursor.execute("SELECT actor_id FROM actor_aliases WHERE alias_name = ?", (normalized_name,))
            row = cursor.fetchone()
            if row:
                logger.debug(f"Found actor ID {row['actor_id']} by alias match for '{normalized_name}'.")
                return row['actor_id']
            logger.debug(f"No actor ID found for name/alias '{normalized_name}'.")
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error while searching for name/alias '{normalized_name}': {e}", exc_info=True)
        return None

def get_aliases_for_actor(db_path: str, actor_id: int) -> List[str]:
    """
    Retrieves all aliases for a given actor_id.

    Args:
        db_path (str): Path to the SQLite database.
        actor_id (int): The ID of the actor.

    Returns:
        List[str]: List of alias strings, empty if none or error.
    """
    if actor_id is None:
        logger.debug("Attempted to get aliases for None actor_id.")
        return []
    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return []
            cursor = conn.cursor()
            cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ? ORDER BY alias_name COLLATE NOCASE", (actor_id,))
            rows = cursor.fetchall()
            aliases = [row['alias_name'] for row in rows]
            logger.debug(f"Found {len(aliases)} aliases for actor ID {actor_id}.")
            return aliases
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching aliases for actor ID {actor_id}: {e}", exc_info=True)
        return []

def get_actor_name_by_id(db_path: str, actor_id: int) -> Optional[str]:
    """
    Retrieves an actor's name by their ID.

    Args:
        db_path (str): Path to the SQLite database.
        actor_id (int): The ID of the actor.

    Returns:
        Optional[str]: Actor's name if found, else None.
    """
    if actor_id is None:
        logger.debug("Attempted to get actor name for None actor_id.")
        return None
    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return None
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM actors WHERE id = ?", (actor_id,))
            row = cursor.fetchone()
            if row:
                logger.debug(f"Found name '{row['name']}' for actor ID {actor_id}.")
                return row['name']
            else:
                logger.warning(f"Actor with ID {actor_id} not found.")
                return None
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching name for actor ID {actor_id}: {e}", exc_info=True)
        return None

def get_all_actors_with_aliases(db_path: str) -> List[Dict[str, Union[int, str, List[str]]]]:
    """
    Retrieves all actors and their associated aliases, ordered by actor name.

    Args:
        db_path (str): Path to the SQLite database.

    Returns:
        List[Dict[str, Union[int, str, List[str]]]]:
            List of {'id', 'name', 'aliases'}, empty on error.
    """
    actors_data: List[Dict[str, Union[int, str, List[str]]]] = []
    try:
        with _get_db_connection(db_path) as conn:
            if not conn: return []
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM actors ORDER BY name COLLATE NOCASE")
            all_actors_rows = cursor.fetchall()
            for actor_row in all_actors_rows:
                actor_id: int = actor_row['id']
                actor_name: str = actor_row['name']
                # Re-using the same cursor for sub-queries is fine with sqlite3
                cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ? ORDER BY alias_name COLLATE NOCASE", (actor_id,))
                aliases_rows = cursor.fetchall()
                aliases: List[str] = [alias_row['alias_name'] for alias_row in aliases_rows]
                actors_data.append({'id': actor_id, 'name': actor_name, 'aliases': aliases})
        logger.info(f"Retrieved {len(actors_data)} actors with their aliases.")
        return actors_data
    except sqlite3.Error as e:
        logger.error(f"Database error in get_all_actors_with_aliases: {e}", exc_info=True) # Corrected logger call
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_all_actors_with_aliases: {e}", exc_info=True)
        return []

if __name__ == '__main__':
    # Configure logging specifically for this test run for clarity
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s', force=True)

    # Add project root to sys.path to allow importing 'database' package
    import sys # ensure sys is imported in this scope
    current_script_dir_main: str = os.path.dirname(os.path.abspath(__file__))
    project_root_dir_main: str = os.path.dirname(current_script_dir_main)
    if project_root_dir_main not in sys.path:
        sys.path.insert(0, project_root_dir_main)

    TEST_ACTOR_DB_PATH: str = os.path.join(_PROJECT_ROOT, 'database', 'actor_management_test.db')

    logger.info(f"--- Testing actor_management.py with dedicated test DB: {TEST_ACTOR_DB_PATH} ---")

    if os.path.exists(TEST_ACTOR_DB_PATH):
        os.remove(TEST_ACTOR_DB_PATH)
        logger.info(f"Removed old test database: {TEST_ACTOR_DB_PATH}")

    try:
        from database.database_setup import create_connection as setup_create_conn
        from database.database_setup import create_all_tables, insert_sample_data

        test_conn = setup_create_conn(TEST_ACTOR_DB_PATH)
        if test_conn:
            logger.info(f"Creating tables in {TEST_ACTOR_DB_PATH}...")
            if not create_all_tables(test_conn):
                logger.critical("Failed to create tables for test DB. Aborting tests.")
                sys.exit(1)
            logger.info(f"Inserting sample data into {TEST_ACTOR_DB_PATH}...")
            if not insert_sample_data(test_conn):
                 logger.warning("Sample data insertion for test DB had issues.")
            test_conn.commit()
            test_conn.close()
            logger.info("Test database schema and sample data created successfully.")
        else:
            logger.critical(f"Failed to connect to test DB {TEST_ACTOR_DB_PATH} for setup. Aborting.")
            sys.exit(1)

    except ImportError as ie:
        logger.error(f"Could not import from database_setup.py: {ie}. Schema might be missing for tests.", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error setting up test DB using database_setup functions: {e}", exc_info=True)
        sys.exit(1)

    logger.info("\n--- Running Actor Management Tests ---")

    actor1_id = add_actor(TEST_ACTOR_DB_PATH, "Test Actor Main")
    assert actor1_id is not None, "Test 1 Failed: Add new actor"
    logger.info(f"Test 1 Passed: Added 'Test Actor Main' with ID {actor1_id}")

    existing_id = add_actor(TEST_ACTOR_DB_PATH, "Test Actor Main")
    assert existing_id == actor1_id, "Test 2 Failed: Add existing actor"
    logger.info(f"Test 2 Passed: Adding existing 'Test Actor Main' returned ID {existing_id}")

    success_alias = add_alias(TEST_ACTOR_DB_PATH, actor1_id, "TAM")
    assert success_alias, "Test 3 Failed: Add new alias"
    logger.info("Test 3 Passed: Added alias 'TAM'")

    fail_alias_exists = add_alias(TEST_ACTOR_DB_PATH, actor1_id, "TAM")
    assert not fail_alias_exists, "Test 4 Failed: Add existing alias for same actor"
    logger.info("Test 4 Passed: Attempt to re-add 'TAM' for same actor failed as expected.")

    actor_john_doe_id = 1
    fail_alias_global = add_alias(TEST_ACTOR_DB_PATH, actor_john_doe_id, "TAM")
    assert not fail_alias_global, "Test 5 Failed: Add alias already existing globally"
    logger.info("Test 5 Passed: Attempt to add globally existing alias 'TAM' to John Doe failed.")

    fail_alias_bad_actor = add_alias(TEST_ACTOR_DB_PATH, 9999, "GhostAlias")
    assert not fail_alias_bad_actor, "Test 6 Failed: Add alias for non-existent actor"
    logger.info("Test 6 Passed: Attempt to add alias for non-existent actor ID 9999 failed.")

    found_id_main = get_actor_id_by_name_or_alias(TEST_ACTOR_DB_PATH, "Test Actor Main")
    assert found_id_main == actor1_id, "Test 7 Failed: Get ID by main name"
    logger.info(f"Test 7 Passed: Found ID {found_id_main} for 'Test Actor Main'")

    found_id_alias = get_actor_id_by_name_or_alias(TEST_ACTOR_DB_PATH, "TAM")
    assert found_id_alias == actor1_id, "Test 8 Failed: Get ID by alias"
    logger.info(f"Test 8 Passed: Found ID {found_id_alias} for alias 'TAM'")

    found_id_none = get_actor_id_by_name_or_alias(TEST_ACTOR_DB_PATH, "NonExistent Actor")
    assert found_id_none is None, "Test 9 Failed: Get ID for non-existent name"
    logger.info("Test 9 Passed: Non-existent actor correctly not found.")

    aliases_for_a1 = get_aliases_for_actor(TEST_ACTOR_DB_PATH, actor1_id)
    assert sorted(aliases_for_a1) == sorted(["TAM"]), f"Test 10 Failed: Get aliases. Expected ['TAM'], got {aliases_for_a1}"
    logger.info(f"Test 10 Passed: Aliases for actor ID {actor1_id}: {aliases_for_a1}")

    aliases_for_jd = get_aliases_for_actor(TEST_ACTOR_DB_PATH, actor_john_doe_id)
    assert sorted(aliases_for_jd) == sorted(["J. Doe", "Johnny D"]), f"Test 11 Failed: Get John Doe aliases. Expected ['J. Doe', 'Johnny D'], got {aliases_for_jd}"
    logger.info(f"Test 11 Passed: Aliases for John Doe (ID {actor_john_doe_id}): {aliases_for_jd}")

    name_for_a1 = get_actor_name_by_id(TEST_ACTOR_DB_PATH, actor1_id)
    assert name_for_a1 == "Test Actor Main", f"Test 12 Failed: Get name by ID. Expected 'Test Actor Main', got {name_for_a1}"
    logger.info(f"Test 12 Passed: Name for actor ID {actor1_id} is '{name_for_a1}'")

    name_for_none = get_actor_name_by_id(TEST_ACTOR_DB_PATH, 9999)
    assert name_for_none is None, "Test 13 Failed: Get name for non-existent ID"
    logger.info("Test 13 Passed: Non-existent actor ID 9999 correctly returned None for name.")

    logger.info("\n--- Test 14: Get All Actors with Aliases ---")
    all_actors = get_all_actors_with_aliases(TEST_ACTOR_DB_PATH)
    assert len(all_actors) >= 3, f"Test 14 Failed: Expected at least 3 actors, got {len(all_actors)}"
    logger.info(f"Test 14 Passed: Retrieved {len(all_actors)} actors.")
    for actor_data in all_actors:
        logger.debug(f"  Actor: ID={actor_data['id']}, Name='{actor_data['name']}', Aliases={actor_data['aliases']}")
        if actor_data['id'] == actor1_id: # type: ignore
            assert sorted(actor_data['aliases']) == sorted(["TAM"])
        if actor_data['name'] == "John Doe":
            assert sorted(actor_data['aliases']) == sorted(["J. Doe", "Johnny D"])
    logger.info("Verified specific actor data in get_all_actors_with_aliases output.")

    logger.info("--- actor_management.py tests complete ---")
