import pytest
import sqlite3
import os
import sys
from typing import Optional, List, Dict, Any, Union, Tuple

# Add project root to sys.path to allow importing from backend and database module
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# Functions to be tested
from backend.database_operations import update_video_record, _get_db_connection
from database.database_setup import (
    create_all_tables,
    insert_sample_data,
    create_connection as setup_create_connection, # For direct use in one test
)

# --- Pytest Fixtures ---

@pytest.fixture
def db_with_schema_ops() -> sqlite3.Connection:
    """
    Pytest fixture to create an in-memory SQLite database connection,
    initialized with schema and sample data for operations tests.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row  # Important for accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON;")

    # Create schema
    assert create_all_tables(conn), "Failed to create tables in db_with_schema_ops"
    # Insert sample data (John Doe ID 1, Jane Smith ID 2)
    assert insert_sample_data(
        conn
    ), "Failed to insert sample data in db_with_schema_ops"

    conn.commit()  # Ensure sample data is committed
    yield conn
    conn.close()


@pytest.fixture
def file_db_ops(tmp_path) -> str:
    """Pytest fixture to create a temporary database file path for ops tests."""
    db_path = tmp_path / "test_db_ops.db"
    return str(db_path)


# --- Helper Functions for Verification ---

def get_video_by_filepath(
    conn: sqlite3.Connection, filepath: str
) -> Optional[sqlite3.Row]:
    """Helper to fetch a video record by its filepath."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE filepath = ?", (filepath,))
    return cursor.fetchone()


def get_video_actors(
    conn: sqlite3.Connection, video_id: int
) -> List[Tuple[int, int]]:
    """Helper to fetch (video_id, actor_id) for a given video_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT video_id, actor_id FROM video_actors WHERE video_id = ? ORDER BY actor_id",
        (video_id,),
    )
    return cursor.fetchall()


# --- Tests for _get_db_connection ---

def test_get_db_connection_in_memory_ops():
    """Test _get_db_connection for an in-memory database."""
    conn = _get_db_connection(":memory:")
    assert conn is not None, "Failed to create in-memory connection via _get_db_connection"
    # Check if foreign keys are enabled (as _get_db_connection should do this)
    fk_status_row = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert fk_status_row is not None, "PRAGMA foreign_keys query returned no result"
    assert fk_status_row[0] == 1, "Foreign keys not enabled on in-memory connection by _get_db_connection"
    # Check row_factory
    assert conn.row_factory == sqlite3.Row, "_get_db_connection did not set row_factory correctly"
    conn.close()

def test_get_db_connection_file_db_ops(file_db_ops: str):
    """Test _get_db_connection for a file-based database."""
    conn = _get_db_connection(file_db_ops)
    assert conn is not None, f"Failed to create file-based connection at {file_db_ops} via _get_db_connection"
    assert os.path.exists(file_db_ops), "Database file was not created by _get_db_connection"

    fk_status_row = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert fk_status_row is not None, "PRAGMA foreign_keys query returned no result on file DB"
    assert fk_status_row[0] == 1, "Foreign keys not enabled on file connection by _get_db_connection"
    assert conn.row_factory == sqlite3.Row, "_get_db_connection did not set row_factory correctly for file DB"
    conn.close()

def test_get_db_connection_creates_directory(tmp_path):
    """Test that _get_db_connection creates the directory if it doesn't exist."""
    non_existent_dir = tmp_path / "non_existent_subdir_ops"
    db_path_in_new_dir = non_existent_dir / "test_in_new_dir.db"

    assert not os.path.exists(non_existent_dir), "Test precondition: Subdirectory should not exist."

    conn = _get_db_connection(str(db_path_in_new_dir))
    assert conn is not None, "Connection failed when target directory did not exist."
    assert os.path.exists(non_existent_dir), "_get_db_connection did not create the directory."
    assert os.path.exists(db_path_in_new_dir), "_get_db_connection did not create the database file in new directory."
    conn.close()


# --- Tests for update_video_record ---

def test_insert_new_video_no_actors(db_with_schema_ops: sqlite3.Connection):
    """Test inserting a new video record with no actors."""
    filepath = "/test/video1.mp4"
    code = "CODE001"
    title = "Test Video 1"
    publisher = "Test Publisher"
    duration = 120
    std_filename = "[CODE001] Test Video 1.mp4"
    actors_list: List[Dict[str, Union[int, str]]] = [] # No actors

    # Use db_with_schema_ops.execute directly for connection path
    # update_video_record expects a db_path string, not a connection object.
    # Since db_with_schema_ops is in-memory, we can't pass its path.
def test_insert_new_video_with_actors(file_db_ops: str):
    """Test inserting a new video with one valid actor."""
    # Setup file_db_ops with schema and sample data
    conn_setup = setup_create_connection(file_db_ops)
    assert conn_setup is not None
    conn_setup.row_factory = sqlite3.Row
    assert create_all_tables(conn_setup)
    assert insert_sample_data(conn_setup) # John Doe (1), Jane Smith (2)
    conn_setup.commit()
    conn_setup.close()

    filepath = "/test/video_actors.mp4"
    title = "Video With Actors"
    # Actor "John Doe" has ID 1 from sample data
    actors_list: List[Dict[str, Union[int, str]]] = [{"id": 1, "canonical_name": "John Doe"}]

    success = update_video_record(
        file_db_ops, filepath, "ACT001", title, "Pub", 180, "[ACT001] Video With Actors - John Doe.mp4", actors_list
    )
    assert success

    conn_verify = sqlite3.connect(file_db_ops)
    conn_verify.row_factory = sqlite3.Row
    video_row = get_video_by_filepath(conn_verify, filepath)
    assert video_row is not None
    video_id = video_row["id"]

    associated_actors = get_video_actors(conn_verify, video_id)
    assert len(associated_actors) == 1
    assert associated_actors[0]["actor_id"] == 1 # John Doe
    conn_verify.close()


def test_update_existing_video(file_db_ops: str):
    """Test updating an existing video's metadata and actor associations."""
    conn_setup = setup_create_connection(file_db_ops)
    assert conn_setup is not None
    conn_setup.row_factory = sqlite3.Row
    assert create_all_tables(conn_setup)
    assert insert_sample_data(conn_setup)
    conn_setup.commit()

    filepath = "/test/update_me.mp4"
    # Initial insert
    initial_actors: List[Dict[str, Union[int, str]]] = [{"id": 1, "canonical_name": "John Doe"}] # John Doe
    update_video_record(
        file_db_ops, filepath, "UPD001", "Initial Title", "Initial Pub", 100, "file1.mp4", initial_actors
    )

    # Update
    updated_title = "Updated Title for Video"
    updated_publisher = "New Publisher Inc."
    # Add Jane Smith (ID 2), keep John Doe (ID 1)
    updated_actors: List[Dict[str, Union[int, str]]] = [
        {"id": 1, "canonical_name": "John Doe"},
        {"id": 2, "canonical_name": "Jane Smith"}
    ]
    success = update_video_record(
        file_db_ops, filepath, "UPD001-R2", updated_title, updated_publisher, 105, "file1_updated.mp4", updated_actors
    )
    assert success

    conn_verify = sqlite3.connect(file_db_ops)
    conn_verify.row_factory = sqlite3.Row
    video_row = get_video_by_filepath(conn_verify, filepath)
    assert video_row is not None
    assert video_row["title"] == updated_title
    assert video_row["publisher"] == updated_publisher
    assert video_row["code"] == "UPD001-R2"
    assert video_row["duration_seconds"] == 105
    assert video_row["standardized_filename"] == "file1_updated.mp4"

    video_id = video_row["id"]
    associated_actors = get_video_actors(conn_verify, video_id)
    assert len(associated_actors) == 2
    actor_ids_from_db = sorted([row["actor_id"] for row in associated_actors])
    assert actor_ids_from_db == [1, 2] # John Doe and Jane Smith
    conn_verify.close()


def test_actor_association_invalid_id(file_db_ops: str):
    """Test that only actors with valid DB IDs are linked."""
    conn_setup = setup_create_connection(file_db_ops)
    assert conn_setup is not None
    conn_setup.row_factory = sqlite3.Row
    assert create_all_tables(conn_setup)
    assert insert_sample_data(conn_setup)
    conn_setup.commit()
    conn_setup.close()

    filepath = "/test/invalid_actor_link.mp4"
    # Valid John Doe (ID 1), invalid Ghost Actor (ID 999)
    actors_list: List[Dict[str, Union[int, str]]] = [
        {"id": 1, "canonical_name": "John Doe"},
        {"id": 999, "canonical_name": "Ghost Actor"} # This ID does not exist
    ]
    success = update_video_record(
        file_db_ops, filepath, "INV001", "Invalid Actor Test", "Pub", 50, "file_inv.mp4", actors_list
    )
    assert success # The operation itself should succeed, but only link valid actors

    conn_verify = sqlite3.connect(file_db_ops)
    conn_verify.row_factory = sqlite3.Row
    video_row = get_video_by_filepath(conn_verify, filepath)
    assert video_row is not None
    video_id = video_row["id"]

    associated_actors = get_video_actors(conn_verify, video_id)
    assert len(associated_actors) == 1, "Should only link the valid actor"
    assert associated_actors[0]["actor_id"] == 1 # John Doe
    conn_verify.close()


def test_actor_association_clears_old_adds_new(file_db_ops: str):
    """Test that re-updating actor associations correctly clears old ones and adds new ones."""
    conn_setup = setup_create_connection(file_db_ops)
    assert conn_setup is not None
    conn_setup.row_factory = sqlite3.Row
    assert create_all_tables(conn_setup)
    assert insert_sample_data(conn_setup)
    conn_setup.commit()

    filepath = "/test/actor_swap.mkv"
    # Initial: John Doe (1)
    initial_actors: List[Dict[str, Union[int, str]]] = [{"id": 1, "canonical_name": "John Doe"}]
    update_video_record(
        file_db_ops, filepath, "SWAP001", "Actor Swap", "Pub", 70, "swap1.mkv", initial_actors
    )

    conn_verify_initial = sqlite3.connect(file_db_ops)
    conn_verify_initial.row_factory = sqlite3.Row
    video_row_initial = get_video_by_filepath(conn_verify_initial, filepath)
    assert video_row_initial is not None
    video_id = video_row_initial["id"]
    initial_db_actors = get_video_actors(conn_verify_initial, video_id)
    assert len(initial_db_actors) == 1
    assert initial_db_actors[0]["actor_id"] == 1
    conn_verify_initial.close()

    # Update: Remove John Doe, Add Jane Smith (2)
    updated_actors: List[Dict[str, Union[int, str]]] = [{"id": 2, "canonical_name": "Jane Smith"}]
    success = update_video_record(
        file_db_ops, filepath, "SWAP001", "Actor Swap - Phase 2", "Pub", 75, "swap2.mkv", updated_actors
    )
    assert success

    conn_verify_updated = sqlite3.connect(file_db_ops)
    conn_verify_updated.row_factory = sqlite3.Row
    video_row_updated = get_video_by_filepath(conn_verify_updated, filepath) # Re-fetch video_id in case it changed (it shouldn't here)
    assert video_row_updated is not None
    video_id_updated = video_row_updated["id"]
    assert video_id == video_id_updated # Ensure same video record was updated

    updated_db_actors = get_video_actors(conn_verify_updated, video_id_updated)
    assert len(updated_db_actors) == 1, "Should only have one actor after update"
    assert updated_db_actors[0]["actor_id"] == 2 # Jane Smith
    conn_verify_updated.close()


def test_update_video_record_failure_no_video_id(file_db_ops: str, caplog):
    """
    Test that update_video_record returns False if video_id cannot be determined.
    This is hard to trigger if INSERT or UPDATE always works and filepath is unique.
    We can simulate this by trying to update a non-existent filepath *without* providing
    enough info for a successful insert if the logic were different.
    The current `update_video_record` either inserts or updates based on filepath.
    If filepath doesn't exist, it inserts. So, it always gets a video_id.
    The critical log "Could not determine Video ID" is the target.
    This test might be more theoretical for the current code structure.
    We'll test by providing a filepath and then try to break the re-query for video_id (not really possible here).
    However, if a conn was None, it would fail.
    """
    # This test relies on the _get_db_connection returning None.
    # We can achieve this by providing an invalid db_path to update_video_record.
    invalid_db_path = "/non/existent/path/to/db.sqlite"
    success = update_video_record(
        invalid_db_path, "/test/any.mp4", "FAIL01", "Fail Test", "Pub", 30, "fail.mp4", []
    )
    assert not success, "update_video_record should fail with invalid db_path"
    # Check logs (optional, depends on how much detail is needed)
    # assert "Error connecting to database" in caplog.text # This is logged by _get_db_connection

# Cleanup for file_db_ops based tests if it was created outside a fixture that auto-cleans.
# @pytest.fixture(autouse=True)
# def cleanup_file_db_ops(request, file_db_ops):
#     """Cleanup file_db_ops after tests if it was used."""
#     def finalizer():
#         if os.path.exists(file_db_ops):
#             os.remove(file_db_ops)
#     request.addfinalizer(finalizer)
# Note: tmp_path fixture handles its own cleanup.
# The `file_db_ops` fixture uses tmp_path, so it's auto-cleaned.
# The `pytest_temp_ops.db` created in `test_insert_new_video_no_actors` is manually cleaned.
# Refactored test_insert_new_video_no_actors to use file_db_ops, renamed to be the primary test:
def test_insert_new_video_no_actors(file_db_ops: str):
    """Test inserting a new video record with no actors, using file_db_ops fixture."""
    # Setup file_db_ops with schema and sample data
    conn_setup = setup_create_connection(file_db_ops)
    assert conn_setup is not None
    conn_setup.row_factory = sqlite3.Row
    assert create_all_tables(conn_setup)
    assert insert_sample_data(conn_setup)
    conn_setup.commit()
    conn_setup.close()

    filepath = "/test/video1.mp4"
    code = "CODE001"
    title = "Test Video 1"
    publisher = "Test Publisher"
    duration = 120
    std_filename = "[CODE001] Test Video 1.mp4"
    actors_list: List[Dict[str, Union[int, str]]] = []

    success = update_video_record(
        file_db_ops, filepath, code, title, publisher, duration, std_filename, actors_list
    )
    assert success, "update_video_record reported failure for new video insert"

    conn_verify = sqlite3.connect(file_db_ops)
    conn_verify.row_factory = sqlite3.Row
    video_row = get_video_by_filepath(conn_verify, filepath)
    assert video_row is not None, "Video was not inserted"
    assert video_row["code"] == code
    assert video_row["title"] == title
    assert video_row["publisher"] == publisher
    assert video_row["duration_seconds"] == duration
    assert video_row["standardized_filename"] == std_filename

    video_id = video_row["id"]
    associated_actors = get_video_actors(conn_verify, video_id)
    assert len(associated_actors) == 0, "Actors should not be associated"
    conn_verify.close()
    # No need to manually remove file_db_ops, tmp_path fixture handles it.
