import unittest
import sys
import os
import sqlite3
import subprocess

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.actor_management import (
    add_actor,
    add_alias,
    get_actor_id_by_name_or_alias,
    get_aliases_for_actor,
    get_actor_name_by_id
)

# Define path for the test database
TEST_DB_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DB_PATH = os.path.join(TEST_DB_DIR, 'test_actors.db')
DB_SETUP_SCRIPT_PATH = os.path.join(os.path.dirname(TEST_DB_DIR), 'database', 'database_setup.py')

class TestActorManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the database once for all tests in this class."""
        # Ensure the directory for the test DB exists
        os.makedirs(TEST_DB_DIR, exist_ok=True)
        # Remove any existing test DB file to start fresh
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

        # Run the database_setup.py script to create tables in the test_actors.db
        # We need to temporarily override the DB path used by database_setup.py
        # This is tricky if database_setup.py hardcodes its DB path.
        # For this test, we assume database_setup.py creates 'video_management.db'
        # in its own directory. We'll copy it or run it in a way that it uses TEST_DB_PATH.

        # Simplest approach: database_setup.py creates its own DB.
        # We then connect to our TEST_DB_PATH and create schema manually or via subprocess
        # For now, let's assume database_setup.py can be pointed to a specific DB or we manually setup.
        # The prompt implies database_setup.py logic should be run for TEST_DB_PATH.
        # If database_setup.py always creates 'database/video_management.db',
        # we'll have to replicate its schema creation here for TEST_DB_PATH or modify setup script.

        # Let's try to run database_setup.py and have it create the schema in TEST_DB_PATH.
        # This requires database_setup.py to be adaptable or we copy the schema.
        # For now, using subprocess and hoping database_setup.py can be influenced or creates a known schema.
        # A better way would be for database_setup.py to accept a db_path argument.
        # Since it doesn't, we'll execute it and assume it creates the main DB,
        # then for testing, we'll create the schema directly in TEST_DB_PATH.

        try:
            conn = sqlite3.connect(TEST_DB_PATH)
            cursor = conn.cursor()
            # Replicating schema from database_setup.py
            cursor.execute("""CREATE TABLE IF NOT EXISTS videos (
                                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, title TEXT,
                                publisher TEXT, duration_seconds INTEGER, filepath TEXT UNIQUE,
                                standardized_filename TEXT);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS actors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS video_actors (
                                video_id INTEGER, actor_id INTEGER, PRIMARY KEY (video_id, actor_id),
                                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                                FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS actor_aliases (
                                id INTEGER PRIMARY KEY AUTOINCREMENT, alias_name TEXT UNIQUE NOT NULL,
                                actor_id INTEGER, FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE);""")
            conn.commit()
        finally:
            if conn:
                conn.close()
        print(f"Test database {TEST_DB_PATH} schema created for TestActorManagement.")


    @classmethod
    def tearDownClass(cls):
        """Remove the test database file after all tests in this class."""
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"Test database {TEST_DB_PATH} removed.")

    def setUp(self):
        """Clear data from tables before each test method."""
        try:
            conn = sqlite3.connect(TEST_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM actor_aliases;")
            cursor.execute("DELETE FROM video_actors;") # Though not directly tested here, good practice
            cursor.execute("DELETE FROM actors;")
            # No need to delete from videos as this class focuses on actors
            conn.commit()
        finally:
            if conn:
                conn.close()

    def test_add_actor(self):
        actor1_id = add_actor(TEST_DB_PATH, "Actor One")
        self.assertIsNotNone(actor1_id)

        actor2_id = add_actor(TEST_DB_PATH, "Actor Two")
        self.assertIsNotNone(actor2_id)
        self.assertNotEqual(actor1_id, actor2_id)

        # Adding existing actor
        existing_actor_id = add_actor(TEST_DB_PATH, "Actor One")
        self.assertEqual(actor1_id, existing_actor_id)

        # Test adding actor with empty name
        empty_name_id = add_actor(TEST_DB_PATH, "")
        self.assertIsNone(empty_name_id)


    def test_add_alias(self):
        actor_id = add_actor(TEST_DB_PATH, "Alias Test Actor")
        self.assertIsNotNone(actor_id)

        self.assertTrue(add_alias(TEST_DB_PATH, actor_id, "ATA1"))
        self.assertTrue(add_alias(TEST_DB_PATH, actor_id, "ata two")) # Test case sensitivity for alias storage

        # Alias already exists for this actor
        self.assertFalse(add_alias(TEST_DB_PATH, actor_id, "ATA1"))

        # Add another actor
        actor2_id = add_actor(TEST_DB_PATH, "Another Actor for Alias")
        self.assertIsNotNone(actor2_id)

        # Alias already exists for a different actor (should fail due to UNIQUE constraint on alias_name)
        self.assertFalse(add_alias(TEST_DB_PATH, actor2_id, "ATA1"))

        # Alias for non-existent actor ID
        self.assertFalse(add_alias(TEST_DB_PATH, 9999, "GhostAlias"))

        # Empty alias name
        self.assertFalse(add_alias(TEST_DB_PATH, actor_id, ""))


    def test_get_actor_id_by_name_or_alias(self):
        actor_id = add_actor(TEST_DB_PATH, "Searchable Actor")
        self.assertIsNotNone(actor_id)
        add_alias(TEST_DB_PATH, actor_id, "SearchAlias")

        # By main name
        self.assertEqual(get_actor_id_by_name_or_alias(TEST_DB_PATH, "Searchable Actor"), actor_id)
        # By its own alias
        self.assertEqual(get_actor_id_by_name_or_alias(TEST_DB_PATH, "SearchAlias"), actor_id)

        # Test another actor and alias to ensure no crosstalk and correct ID resolution
        other_actor_name = "Other Searchable"
        other_actor_id = add_actor(TEST_DB_PATH, other_actor_name)
        self.assertIsNotNone(other_actor_id)
        add_alias(TEST_DB_PATH, other_actor_id, "OtherAlias123")
        self.assertEqual(get_actor_id_by_name_or_alias(TEST_DB_PATH, other_actor_name), other_actor_id)
        self.assertEqual(get_actor_id_by_name_or_alias(TEST_DB_PATH, "OtherAlias123"), other_actor_id)

        # Non-existent name/alias
        self.assertIsNone(get_actor_id_by_name_or_alias(TEST_DB_PATH, "NonExistent"))
        # Empty name
        self.assertIsNone(get_actor_id_by_name_or_alias(TEST_DB_PATH, ""))


    def test_get_aliases_for_actor(self):
        actor_id = add_actor(TEST_DB_PATH, "Actor With Aliases")
        self.assertIsNotNone(actor_id)
        add_alias(TEST_DB_PATH, actor_id, "Alias1")
        add_alias(TEST_DB_PATH, actor_id, "Alias2")

        aliases = get_aliases_for_actor(TEST_DB_PATH, actor_id)
        self.assertIsInstance(aliases, list)
        self.assertCountEqual(aliases, ["Alias1", "Alias2"]) # Order doesn't matter

        # Actor with no aliases
        actor_no_alias_id = add_actor(TEST_DB_PATH, "Actor No Alias")
        self.assertIsNotNone(actor_no_alias_id)
        self.assertEqual(get_aliases_for_actor(TEST_DB_PATH, actor_no_alias_id), [])

        # Non-existent actor ID
        self.assertEqual(get_aliases_for_actor(TEST_DB_PATH, 9999), [])


    def test_get_actor_name_by_id(self):
        actor_name = "Named Actor"
        actor_id = add_actor(TEST_DB_PATH, actor_name)
        self.assertIsNotNone(actor_id)

        self.assertEqual(get_actor_name_by_id(TEST_DB_PATH, actor_id), actor_name)

        # Non-existent ID
        self.assertIsNone(get_actor_name_by_id(TEST_DB_PATH, 9999))
        # None ID
        self.assertIsNone(get_actor_name_by_id(TEST_DB_PATH, None))

if __name__ == '__main__':
    unittest.main()
