import sqlite3
import os

def _get_db_connection(db_path):
    """Helper function to get a database connection."""
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Using sqlite3.Row to access columns by name is good for SELECTs,
    # but not strictly necessary for INSERT/UPDATE if we don't fetch results immediately by name.
    # conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;") # Ensure foreign key constraints are enforced
    return conn

def update_video_record(db_path, original_filepath, code, title, publisher, duration_seconds, standardized_filename, actors_list):
    """
    Inserts or updates a video record in the 'videos' table and manages actor associations.
    'actors_list' is a list of dicts, e.g., [{'id': actor_id, 'canonical_name': ...}]
    """
    video_id = None
    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO videos (filepath, code, title, publisher, duration_seconds, standardized_filename)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (original_filepath, code, title, publisher, duration_seconds, standardized_filename))
                video_id = cursor.lastrowid
                print(f"Inserted new video record for '{original_filepath}', Video ID: {video_id}")
            except sqlite3.IntegrityError: # Likely UNIQUE constraint on filepath
                print(f"Video record for '{original_filepath}' likely exists. Attempting update.")
                cursor.execute("""
                    UPDATE videos
                    SET code=?, title=?, publisher=?, duration_seconds=?, standardized_filename=?
                    WHERE filepath=?
                """, (code, title, publisher, duration_seconds, standardized_filename, original_filepath))

                # After an update, we need to fetch the video_id
                cursor.execute("SELECT id FROM videos WHERE filepath=?", (original_filepath,))
                video_id_row = cursor.fetchone()
                if video_id_row:
                    video_id = video_id_row[0]
                    print(f"Updated video record for '{original_filepath}', Video ID: {video_id}")
                else:
                    # This should not happen if the IntegrityError was due to the filepath UNIQUE constraint
                    print(f"CRITICAL Error: Could not find Video ID for '{original_filepath}' after supposed update.")
                    return # Exit if we can't get video_id

            if video_id is None:
                print(f"Error: video_id is None for '{original_filepath}'. Cannot manage actor associations.")
                return

            # Manage video-actor associations
            # 1. Delete existing associations for this video_id
            cursor.execute("DELETE FROM video_actors WHERE video_id=?", (video_id,))

            # 2. Insert new associations
            actors_added_count = 0
            if actors_list: # Ensure actors_list is not None or empty
                for actor in actors_list:
                    actor_db_id = actor.get('id') # Get the actor's ID from the database
                    if actor_db_id is not None:
                        try:
                            cursor.execute("INSERT INTO video_actors (video_id, actor_id) VALUES (?, ?)", (video_id, actor_db_id))
                            actors_added_count += 1
                        except sqlite3.IntegrityError as e:
                            # This could happen if actor_id doesn't exist in actors table (FK constraint)
                            # Or if the (video_id, actor_id) pair somehow violates PK (shouldn't after delete)
                            print(f"Warning: Could not add association for video ID {video_id} and actor ID {actor_db_id}. Error: {e}")
                    else:
                        print(f"Warning: Actor '{actor.get('canonical_name', 'Unknown Name')}' does not have a database ID. Skipping association.")

            conn.commit()
            print(f"Successfully updated/inserted video and {actors_added_count} actor links for '{original_filepath}' (Video ID: {video_id})")

    except sqlite3.Error as e:
        print(f"Database error in update_video_record for '{original_filepath}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred in update_video_record for '{original_filepath}': {e}")

if __name__ == '__main__':
    # Basic test (requires database_setup.py to have run)
    # Construct path to DB, assuming this script is in backend/
    db_dir_for_test = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database')
    test_db_path = os.path.join(db_dir_for_test, 'video_management.db')

    print(f"Testing database_operations.py with DB: {test_db_path}")

    if not os.path.exists(test_db_path):
        print("Test database not found. Please run database_setup.py first.")
    else:
        # Example 1: New video
        print("\n--- Test 1: New Video ---")
        actors1 = [{'id': 1, 'canonical_name': 'John Doe'}] # Assuming John Doe has ID 1
        update_video_record(test_db_path,
                            "/path/to/new_video.mp4",
                            "NEW-001", "New Video Title", "New Publisher",
                            120, # duration_seconds
                            "[NEW-001] New Video Title - John Doe.mp4",
                            actors1)

        # Example 2: Update existing video (the one just added)
        print("\n--- Test 2: Update Video ---")
        actors2 = [{'id': 1, 'canonical_name': 'John Doe'}, {'id': 2, 'canonical_name': 'Jane Smith'}] # Add Jane Smith (ID 2)
        update_video_record(test_db_path,
                            "/path/to/new_video.mp4",
                            "NEW-001-UPD", "Updated Title", "Updated Publisher",
                            125,
                            "[NEW-001-UPD] Updated Title - John Doe, Jane Smith.mp4",
                            actors2)

        # Example 3: Video with no actors
        print("\n--- Test 3: Video with no actors ---")
        update_video_record(test_db_path,
                            "/path/to/no_actor_video.avi",
                            "NA-002", "No Actors Here", "Solo Productions",
                            60,
                            "[NA-002] No Actors Here.avi",
                            [])

        # Example 4: Video with an actor not in DB (should skip association)
        print("\n--- Test 4: Video with non-DB actor ID ---")
        actors4 = [{'id': 999, 'canonical_name': 'Ghost Actor'}] # Assuming ID 999 doesn't exist
        update_video_record(test_db_path,
                            "/path/to/ghost_actor_video.mkv",
                            "GHOST-003", "Ghost in the Machine", "Phantom Films",
                            90,
                            "[GHOST-003] Ghost in the Machine - Ghost Actor.mkv",
                            actors4)

        print("\n--- Verifying Data (Manual Check Recommended) ---")
        # Simple verification
        try:
            conn = _get_db_connection(test_db_path)
            cursor = conn.cursor()
            print("\nVideos table:")
            for row in cursor.execute("SELECT id, filepath, standardized_filename, title FROM videos ORDER BY id DESC LIMIT 5"):
                print(dict(row))
            print("\nVideo_actors table (for new_video.mp4 - should reflect Test 2):")
            # Need to get video_id for /path/to/new_video.mp4
            cursor.execute("SELECT id FROM videos WHERE filepath = ?", ("/path/to/new_video.mp4",))
            v_id_row = cursor.fetchone()
            if v_id_row:
                for row in cursor.execute("SELECT video_id, actor_id FROM video_actors WHERE video_id = ?", (v_id_row[0],)):
                    print(dict(row))
            conn.close()
        except Exception as e:
            print(f"Error during verification: {e}")
