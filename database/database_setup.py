import sqlite3
import os
import logging
from typing import Optional, List, Tuple

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# Define database path at module level
DATABASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME: str = os.path.join(DATABASE_DIR, 'video_management.db')

def create_connection(db_path: str = DATABASE_NAME) -> Optional[sqlite3.Connection]:
    """
    Create a database connection to the SQLite database specified by db_path.
    Enforces foreign key constraints upon connection.

    Args:
        db_path (str): The path to the database file.

    Returns:
        Optional[sqlite3.Connection]: A database connection object or None if connection fails.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        # Ensure the directory for the database exists
        db_dir_path = os.path.dirname(db_path)
        if db_dir_path and not os.path.exists(db_dir_path):
            os.makedirs(db_dir_path, exist_ok=True)
            logging.info(f"Created database directory: {db_dir_path}")

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        logging.info(f"Successfully connected to SQLite database: {db_path} with foreign keys ON.")
    except sqlite3.Error as e:
        logging.error(f"Error connecting to database '{db_path}': {e}", exc_info=True)
    return conn

def create_table(conn: sqlite3.Connection, create_table_sql: str) -> bool:
    """
    Create a table from the create_table_sql statement.

    Args:
        conn (sqlite3.Connection): Connection object to the SQLite database.
        create_table_sql (str): A CREATE TABLE statement.

    Returns:
        bool: True if table was created successfully or already existed, False otherwise.
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit() # Commit after each table creation for clarity
        return True
    except sqlite3.Error as e:
        logging.error(f"Error creating table with SQL: {create_table_sql.splitlines()[0]}... Error: {e}", exc_info=True)
        return False

def create_all_tables(conn: sqlite3.Connection) -> bool:
    """
    Creates all necessary tables in the database.

    Args:
        conn (sqlite3.Connection): Connection object to the SQLite database.

    Returns:
        bool: True if all tables were created successfully, False otherwise.
    """
    sql_create_videos_table = """CREATE TABLE IF NOT EXISTS videos (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    code TEXT,
                                    title TEXT,
                                    publisher TEXT,
                                    duration_seconds INTEGER,
                                    filepath TEXT UNIQUE,
                                    standardized_filename TEXT
                                );"""

    sql_create_actors_table = """CREATE TABLE IF NOT EXISTS actors (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT UNIQUE NOT NULL
                                );"""

    sql_create_video_actors_table = """CREATE TABLE IF NOT EXISTS video_actors (
                                        video_id INTEGER,
                                        actor_id INTEGER,
                                        PRIMARY KEY (video_id, actor_id),
                                        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                                        FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE
                                    );"""

    sql_create_actor_aliases_table = """CREATE TABLE IF NOT EXISTS actor_aliases (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        alias_name TEXT UNIQUE NOT NULL,
                                        actor_id INTEGER,
                                        FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE
                                    );"""

    tables_to_create: List[Tuple[str, str]] = [
        ("videos", sql_create_videos_table),
        ("actors", sql_create_actors_table),
        ("video_actors", sql_create_video_actors_table),
        ("actor_aliases", sql_create_actor_aliases_table)
    ]

    all_successful = True
    for table_name, sql_statement in tables_to_create:
        if create_table(conn, sql_statement):
            logging.info(f"Table '{table_name}' created successfully or already exists.")
        else:
            logging.error(f"Failed to create table '{table_name}'.")
            all_successful = False
            break # Stop if one table creation fails

    return all_successful

def _get_or_create_actor(cursor: sqlite3.Cursor, actor_name: str) -> Optional[int]:
    """
    Helper function to get an actor's ID if they exist, or create them and return the new ID.

    Args:
        cursor (sqlite3.Cursor): The database cursor.
        actor_name (str): The name of the actor.

    Returns:
        Optional[int]: The actor's ID, or None if an error occurs.
    """
    try:
        cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
        row = cursor.fetchone()
        if row:
            logging.info(f"Actor '{actor_name}' found with ID: {row[0]}.")
            return row[0]
        else:
            cursor.execute("INSERT INTO actors (name) VALUES (?)", (actor_name,))
            new_id = cursor.lastrowid
            logging.info(f"Actor '{actor_name}' inserted with new ID: {new_id}.")
            return new_id
    except sqlite3.Error as e:
        logging.error(f"Error getting or creating actor '{actor_name}': {e}", exc_info=True)
        return None


def insert_sample_data(conn: sqlite3.Connection) -> bool:
    """
    Inserts sample data (actors and aliases) into the database.

    Args:
        conn (sqlite3.Connection): Connection object to the SQLite database.

    Returns:
        bool: True if sample data insertion was generally successful, False otherwise.
              Note: Individual alias insertion failures are logged but don't make the whole function fail.
    """
    cursor = conn.cursor()
    actors_with_aliases: List[Tuple[str, List[str]]] = [
        ("John Doe", ["Johnny D", "J. Doe"]),
        ("Jane Smith", ["Janie S"])
    ]

    overall_success = True

    for actor_name, aliases in actors_with_aliases:
        actor_id = _get_or_create_actor(cursor, actor_name)
        if actor_id is None:
            overall_success = False
            continue # Skip aliases if actor couldn't be processed

        for alias_name in aliases:
            try:
                # Check if alias already exists for this actor or any other actor
                cursor.execute("SELECT actor_id FROM actor_aliases WHERE alias_name = ?", (alias_name,))
                existing_alias_row = cursor.fetchone()
                if existing_alias_row:
                    if existing_alias_row[0] == actor_id:
                        logging.info(f"Alias '{alias_name}' already exists for actor '{actor_name}'. Skipping.")
                    else:
                        # This indicates alias is tied to a different actor, which shouldn't happen if DB is clean
                        # or if alias was unique. The UNIQUE constraint on alias_name handles this mostly.
                        logging.warning(f"Alias '{alias_name}' found but tied to a different actor ID ({existing_alias_row[0]}). Skipping for actor '{actor_name}'.")
                else:
                    cursor.execute("INSERT INTO actor_aliases (actor_id, alias_name) VALUES (?, ?)", (actor_id, alias_name))
                    logging.info(f"Alias '{alias_name}' added for actor '{actor_name}' (ID: {actor_id}).")
            except sqlite3.IntegrityError as ie: # Handles UNIQUE constraint on alias_name
                logging.warning(f"Could not insert alias '{alias_name}' for actor '{actor_name}' (ID: {actor_id}). Likely already exists. Error: {ie}")
            except sqlite3.Error as e:
                logging.error(f"Error inserting alias '{alias_name}' for actor '{actor_name}' (ID: {actor_id}): {e}", exc_info=True)
                overall_success = False # Consider this a more serious failure

    if overall_success:
        conn.commit()
        logging.info("Sample data insertion process completed.")
    else:
        conn.rollback() # Rollback if there were issues beyond just existing aliases
        logging.warning("Sample data insertion encountered errors. Rolled back transactions for this step.")

    return overall_success


def main() -> None:
    """
    Main function to set up the database: create connection, tables, and insert sample data.
    """
    logging.info(f"Starting database setup for: {DATABASE_NAME}")

    conn = create_connection() # Uses default DATABASE_NAME

    if conn is not None:
        try:
            if not create_all_tables(conn):
                logging.error("Database setup failed: Not all tables could be created. Aborting.")
                return # Exit if table creation fails

            if not insert_sample_data(conn):
                logging.warning("There were issues during sample data insertion. Check logs.")

            logging.info("Database setup process finished.")

        except Exception as e: # Catch any other unexpected errors during the process
            logging.error(f"An unexpected error occurred during database setup: {e}", exc_info=True)
        finally:
            conn.close()
            logging.info("Database connection closed.")
    else:
        logging.error("Database setup failed: Could not create database connection. Aborting.")

if __name__ == '__main__':
    main()
