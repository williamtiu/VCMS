import sqlite3
import os

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(DATABASE_DIR, 'video_management.db')

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        print(f"Successfully connected to SQLite database: {DATABASE_NAME}")
    except sqlite3.Error as e:
        print(e)
    return conn

def create_table(conn, create_table_sql):
    """Create a table from the create_table_sql statement."""
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except sqlite3.Error as e:
        print(e)

def main():
    conn = create_connection()

    if conn is not None:
        # Create videos table
        create_videos_table_sql = """CREATE TABLE IF NOT EXISTS videos (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        code TEXT,
                                        title TEXT,
                                        publisher TEXT,
                                        duration_seconds INTEGER,
                                        filepath TEXT UNIQUE,
                                        standardized_filename TEXT
                                    );"""
        create_table(conn, create_videos_table_sql)
        print("Created 'videos' table (if it didn't exist).")

        # Create actors table
        create_actors_table_sql = """CREATE TABLE IF NOT EXISTS actors (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        name TEXT UNIQUE NOT NULL
                                    );"""
        create_table(conn, create_actors_table_sql)
        print("Created 'actors' table (if it didn't exist).")

        # Create video_actors table
        create_video_actors_table_sql = """CREATE TABLE IF NOT EXISTS video_actors (
                                            video_id INTEGER,
                                            actor_id INTEGER,
                                            PRIMARY KEY (video_id, actor_id),
                                            FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                                            FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE
                                        );"""
        create_table(conn, create_video_actors_table_sql)
        print("Created 'video_actors' table (if it didn't exist).")

        # Create actor_aliases table
        create_actor_aliases_table_sql = """CREATE TABLE IF NOT EXISTS actor_aliases (
                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            alias_name TEXT UNIQUE NOT NULL,
                                            actor_id INTEGER,
                                            FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE
                                        );"""
        create_table(conn, create_actor_aliases_table_sql)
        print("Created 'actor_aliases' table (if it didn't exist).")

        # Insert sample data
        cursor = conn.cursor()
        try:
            # John Doe
            cursor.execute("INSERT OR IGNORE INTO actors (name) VALUES (?)", ("John Doe",))
            john_doe_id = cursor.lastrowid
            if john_doe_id == 0: # Actor likely already exists
                cursor.execute("SELECT id FROM actors WHERE name = ?", ("John Doe",))
                john_doe_id = cursor.fetchone()[0]

            if john_doe_id: # Proceed if actor_id is valid
                 aliases_john = [("Johnny D", john_doe_id), ("J. Doe", john_doe_id)]
                 cursor.executemany("INSERT OR IGNORE INTO actor_aliases (alias_name, actor_id) VALUES (?, ?)", aliases_john)
                 print(f"Inserted/updated actor John Doe (ID: {john_doe_id}) and their aliases.")


            # Jane Smith
            cursor.execute("INSERT OR IGNORE INTO actors (name) VALUES (?)", ("Jane Smith",))
            jane_smith_id = cursor.lastrowid
            if jane_smith_id == 0: # Actor likely already exists
                cursor.execute("SELECT id FROM actors WHERE name = ?", ("Jane Smith",))
                jane_smith_id = cursor.fetchone()[0]

            if jane_smith_id: # Proceed if actor_id is valid
                aliases_jane = [("Janie S", jane_smith_id)]
                cursor.executemany("INSERT OR IGNORE INTO actor_aliases (alias_name, actor_id) VALUES (?, ?)", aliases_jane)
                print(f"Inserted/updated actor Jane Smith (ID: {jane_smith_id}) and their aliases.")

            conn.commit()
        except sqlite3.Error as e:
            print(f"Error inserting sample data: {e}")
        finally:
            conn.close()
            print("SQLite connection closed.")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()
