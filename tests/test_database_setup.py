import pytest
import sqlite3
import os
import sys
from typing import Optional, List, Tuple

# Add project root to sys.path to allow importing from database module
# This assumes tests are run from the project root (e.g., python -m pytest)
# or that PYTHONPATH is set up appropriately.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# Functions to be tested
from database.database_setup import (
    create_connection,
    create_table, # create_table is used by create_all_tables
    create_all_tables,
    insert_sample_data,
    _get_or_create_actor, # Also test this helper if it's complex enough
    DATABASE_NAME as MODULE_DB_NAME # Default DB name used by create_connection
)

# --- Test Fixtures (if needed, e.g., for a common in-memory DB) ---

@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Pytest fixture to create an in-memory SQLite database connection."""
    conn = sqlite3.connect(":memory:")
    # Enable foreign keys for this connection, similar to create_connection
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row # For accessing columns by name
    yield conn
    conn.close()

@pytest.fixture
def file_db(tmp_path) -> str:
    """Pytest fixture to create a temporary database file path."""
    db_path = tmp_path / "test_db_setup.db"
    return str(db_path)


# --- Tests for create_connection ---

def test_create_connection_in_memory():
    """Test creating an in-memory database connection."""
    conn = create_connection(":memory:")
    assert conn is not None, "Failed to create in-memory connection"
    # Check if foreign keys are enabled
    fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert fk_status[0] == 1, "Foreign keys not enabled on in-memory connection"
    conn.close()

def test_create_connection_file_db(file_db):
    """Test creating a database connection to a file."""
    conn = create_connection(file_db)
    assert conn is not None, f"Failed to create file-based connection at {file_db}"
    assert os.path.exists(file_db), "Database file was not created"
    fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()
    assert fk_status[0] == 1, "Foreign keys not enabled on file connection"
    conn.close()

def test_create_connection_default_path_creation(tmp_path):
    """Test if create_connection creates the default DB path if it doesn't exist."""
    # This test is a bit tricky as MODULE_DB_NAME is relative to database_setup.py
    # We'll simulate its expected path within tmp_path for isolation.
    # The original MODULE_DB_NAME is database/video_management.db
    # We'll create a temporary 'database' subdir in tmp_path.

    temp_db_dir = tmp_path / "database"
    # We don't create temp_db_dir here, create_connection should do it.

    # Temporarily change DATABASE_NAME for the scope of this test if possible,
    # or test the directory creation aspect of create_connection more directly.
    # The current create_connection uses db_path=DATABASE_NAME as default.
    # Let's test its directory creation logic by giving a path where dir doesn't exist.

    specific_test_db_path = temp_db_dir / "specific_test.db"

    conn = create_connection(str(specific_test_db_path))
    assert conn is not None, "Connection failed"
    assert os.path.exists(temp_db_dir), "Database directory was not created by create_connection"
    assert os.path.exists(specific_test_db_path), "Database file was not created by create_connection"
    conn.close()


# --- Tests for create_table and create_all_tables ---

def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[Tuple]:
    """Helper to get schema information for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    return cursor.fetchall()

def test_create_all_tables_success(in_memory_db: sqlite3.Connection):
    """Test successful creation of all tables."""
    assert create_all_tables(in_memory_db), "create_all_tables reported failure"

    tables_and_expected_columns = {
        "videos": ["id", "code", "title", "publisher", "duration_seconds", "filepath", "standardized_filename"],
        "actors": ["id", "name"],
        "video_actors": ["video_id", "actor_id"],
        "actor_aliases": ["id", "alias_name", "actor_id"]
    }

    for table_name, expected_cols in tables_and_expected_columns.items():
        schema_rows = get_table_schema(in_memory_db, table_name)
        assert len(schema_rows) > 0, f"Table '{table_name}' was not created or is empty."

        # Check for presence of key columns (simplified schema check)
        schema_col_names = [row["name"] for row in schema_rows] # row is sqlite3.Row
        for col in expected_cols:
            assert col in schema_col_names, f"Column '{col}' missing in table '{table_name}'"

    # Check if index on actor_aliases was created
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='actor_aliases' AND name='idx_actor_aliases_actor_id';")
    assert cursor.fetchone() is not None, "Index 'idx_actor_aliases_actor_id' was not created."


def test_create_table_failure(in_memory_db: sqlite3.Connection):
    """Test create_table failure with invalid SQL (simulated)."""
    # create_table itself logs errors, so this test just checks return value.
    # We don't want to actually corrupt the in_memory_db for other tests if it's shared differently.
    # Here, in_memory_db is fresh for each test.
    invalid_sql = "CREATE TABLE IF NOT EXISTS MyInvalidTable (id INTEGER PRIMARY KEY THIS_IS_BAD_SYNTAX);"
    assert not create_table(in_memory_db, invalid_sql), "create_table should return False on error"


# --- Tests for _get_or_create_actor and insert_sample_data ---

@pytest.fixture
def db_with_schema(in_memory_db: sqlite3.Connection) -> sqlite3.Connection:
    """Fixture to provide an in-memory DB with tables created."""
    create_all_tables(in_memory_db)
    return in_memory_db

def test_get_or_create_actor_new(db_with_schema: sqlite3.Connection):
    """Test adding a new actor with _get_or_create_actor."""
    cursor = db_with_schema.cursor()
    actor_name = "New Actor Test"
    actor_id = _get_or_create_actor(cursor, actor_name)
    assert actor_id is not None
    assert isinstance(actor_id, int)

    # Verify actor is in DB
    cursor.execute("SELECT name FROM actors WHERE id = ?", (actor_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["name"] == actor_name

def test_get_or_create_actor_existing(db_with_schema: sqlite3.Connection):
    """Test getting an existing actor with _get_or_create_actor."""
    cursor = db_with_schema.cursor()
    actor_name = "Existing Actor"
    # First, add the actor
    initial_actor_id = _get_or_create_actor(cursor, actor_name)
    assert initial_actor_id is not None

    # Then, try to get/create again
    retrieved_actor_id = _get_or_create_actor(cursor, actor_name)
    assert retrieved_actor_id == initial_actor_id

def test_get_or_create_actor_empty_name(db_with_schema: sqlite3.Connection):
    """Test _get_or_create_actor with an empty name (should be handled by caller or return None)."""
    # Note: _get_or_create_actor itself doesn't currently validate empty string,
    # it relies on DB constraints or caller validation.
    # The function `add_actor` (which uses a similar pattern) does validate.
    # For direct test of _get_or_create_actor, if it allows empty and DB fails, it's a DB error.
    # If DB allows empty unique names (not typical for NOT NULL), it would insert.
    # As per current schema, actors.name is NOT NULL.
    # The _get_or_create_actor function catches sqlite3.Error (including IntegrityError)
    # and returns None in such cases.
    cursor = db_with_schema.cursor()
    actor_id = _get_or_create_actor(cursor, "")
    assert actor_id is None, "Expected None when trying to create actor with empty name due to NOT NULL constraint"

def test_insert_sample_data_initial(db_with_schema: sqlite3.Connection):
    """Test initial insertion of sample data."""
    assert insert_sample_data(db_with_schema), "insert_sample_data reported failure"

    cursor = db_with_schema.cursor()
    # Check John Doe
    cursor.execute("SELECT id FROM actors WHERE name = 'John Doe'")
    john_doe_row = cursor.fetchone()
    assert john_doe_row is not None, "John Doe not found after sample data insertion"
    john_doe_id = john_doe_row["id"]

    cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ? ORDER BY alias_name", (john_doe_id,))
    jd_aliases = [row["alias_name"] for row in cursor.fetchall()]
    assert sorted(jd_aliases) == sorted(["J. Doe", "Johnny D"])

    # Check Jane Smith
    cursor.execute("SELECT id FROM actors WHERE name = 'Jane Smith'")
    jane_smith_row = cursor.fetchone()
    assert jane_smith_row is not None, "Jane Smith not found"
    jane_smith_id = jane_smith_row["id"]

    cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ? ORDER BY alias_name", (jane_smith_id,))
    js_aliases = [row["alias_name"] for row in cursor.fetchall()]
    assert sorted(js_aliases) == sorted(["Janie S"])

def test_insert_sample_data_idempotency(db_with_schema: sqlite3.Connection):
    """Test that running insert_sample_data multiple times does not create duplicates."""
    assert insert_sample_data(db_with_schema), "First call to insert_sample_data failed"
    # Get initial counts/data if needed, or just rely on the function's internal checks

    assert insert_sample_data(db_with_schema), "Second call to insert_sample_data reported failure"

    cursor = db_with_schema.cursor()
    # Check John Doe
    cursor.execute("SELECT id FROM actors WHERE name = 'John Doe'")
    john_doe_id = cursor.fetchone()["id"]
    cursor.execute("SELECT COUNT(*) FROM actor_aliases WHERE actor_id = ?", (john_doe_id,))
    assert cursor.fetchone()[0] == 2, "Duplicate aliases created for John Doe or count mismatch"

    # Check Jane Smith
    cursor.execute("SELECT id FROM actors WHERE name = 'Jane Smith'")
    jane_smith_id = cursor.fetchone()["id"]
    cursor.execute("SELECT COUNT(*) FROM actor_aliases WHERE actor_id = ?", (jane_smith_id,))
    assert cursor.fetchone()[0] == 1, "Duplicate aliases created for Jane Smith or count mismatch"

    # Check total actors (assuming only these two were added by sample_data)
    # This depends on whether _get_or_create_actor is used by other tests on the same fixture instance.
    # Given db_with_schema is function-scoped, this is fine.
    cursor.execute("SELECT COUNT(*) FROM actors")
    assert cursor.fetchone()[0] == 2, "More actors than expected after idempotent sample data insertion"
