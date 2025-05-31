import sqlite3
import os

# Assuming the database is in the 'database' directory relative to the project root.
# For testing, this script might be run from /app, so db_path needs to be correct.
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database')
DEFAULT_DB_PATH = os.path.join(DATABASE_DIR, 'video_management.db')

def _get_db_connection(db_path):
    """Helper function to get a database connection."""
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON;") # Ensure foreign key constraints are enforced
    return conn

def add_actor(db_path, actor_name):
    """
    Adds a new actor to the actors table.
    If the actor already exists, returns the existing actor's ID.
    """
    if not actor_name:
        print("Error: Actor name cannot be empty.")
        return None

    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Check if actor already exists
            cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
            row = cursor.fetchone()
            if row:
                print(f"Actor '{actor_name}' already exists with ID: {row['id']}.")
                return row['id']

            # Add new actor
            cursor.execute("INSERT INTO actors (name) VALUES (?)", (actor_name,))
            conn.commit()
            new_actor_id = cursor.lastrowid
            print(f"Actor '{actor_name}' added with ID: {new_actor_id}.")
            return new_actor_id
    except sqlite3.IntegrityError as e: # Should be caught by the check above, but as a safeguard
        print(f"Error adding actor '{actor_name}': {e}. It might already exist.")
        # Attempt to fetch and return ID if it's an integrity error for uniqueness
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
        row = cursor.fetchone()
        if row:
            return row['id']
        return None
    except sqlite3.Error as e:
        print(f"Database error while adding actor '{actor_name}': {e}")
        return None

def add_alias(db_path, actor_id, alias_name):
    """
    Adds a new alias for the given actor_id to the actor_aliases table.
    Prevents adding an alias if it already exists for any actor or if actor_id is invalid.
    Returns True if alias was added successfully, False otherwise.
    """
    if not alias_name:
        print("Error: Alias name cannot be empty.")
        return False
    if actor_id is None:
        print("Error: Actor ID cannot be None.")
        return False

    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Check if actor_id is valid
            cursor.execute("SELECT id FROM actors WHERE id = ?", (actor_id,))
            if not cursor.fetchone():
                print(f"Error: Actor with ID {actor_id} not found.")
                return False

            # Check if alias_name already exists in actor_aliases for any actor
            cursor.execute("SELECT actor_id FROM actor_aliases WHERE alias_name = ?", (alias_name,))
            row = cursor.fetchone()
            if row:
                if row['actor_id'] == actor_id:
                    print(f"Alias '{alias_name}' already exists for actor ID {actor_id}.")
                else:
                    print(f"Error: Alias '{alias_name}' already exists for a different actor (ID: {row['actor_id']}).")
                return False

            cursor.execute("INSERT INTO actor_aliases (actor_id, alias_name) VALUES (?, ?)", (actor_id, alias_name))
            conn.commit()
            print(f"Alias '{alias_name}' added for actor ID {actor_id}.")
            return True
    except sqlite3.IntegrityError:
        # This can happen if alias_name is not unique (though checked above) or actor_id FK constraint fails
        print(f"Error adding alias '{alias_name}': Alias might already exist or actor ID {actor_id} is invalid.")
        return False
    except sqlite3.Error as e:
        print(f"Database error while adding alias '{alias_name}': {e}")
        return False

def get_actor_id_by_name_or_alias(db_path, name):
    """
    Searches for the given name in actors table (name) and actor_aliases table (alias_name).
    Returns the corresponding unique actor_id if a match is found, otherwise None.
    """
    if not name:
        return None

    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Search in actors table
            cursor.execute("SELECT id FROM actors WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return row['id']

            # Search in actor_aliases table
            cursor.execute("SELECT actor_id FROM actor_aliases WHERE alias_name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return row['actor_id']

            return None # No match found
    except sqlite3.Error as e:
        print(f"Database error while searching for '{name}': {e}")
        return None

def get_aliases_for_actor(db_path, actor_id):
    """
    Retrieves all aliases associated with the given actor_id.
    Returns a list of alias strings.
    """
    if actor_id is None:
        return []

    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ?", (actor_id,))
            rows = cursor.fetchall()
            return [row['alias_name'] for row in rows]
    except sqlite3.Error as e:
        print(f"Database error while fetching aliases for actor ID {actor_id}: {e}")
        return []

def get_actor_name_by_id(db_path, actor_id):
    """
    Retrieves the main name of an actor by their actor_id.
    Returns the actor's name string if found, otherwise None.
    """
    if actor_id is None:
        return None
    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM actors WHERE id = ?", (actor_id,))
            row = cursor.fetchone()
            if row:
                return row['name']
            else:
                print(f"Actor with ID {actor_id} not found.")
                return None
    except sqlite3.Error as e:
        print(f"Database error while fetching name for actor ID {actor_id}: {e}")
        return None

def get_all_actors_with_aliases(db_path):
    """
    Retrieves all actors and their associated aliases.

    Returns:
        list: A list of dictionaries, where each dictionary contains:
              {'id': actor_id, 'name': actor_name, 'aliases': [list_of_aliases]}
              Returns an empty list if no actors are found or in case of an error.
    """
    actors_data = []
    try:
        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Fetch all actors
            cursor.execute("SELECT id, name FROM actors ORDER BY name COLLATE NOCASE")
            all_actors = cursor.fetchall()

            for actor_row in all_actors:
                actor_id = actor_row['id']
                actor_name = actor_row['name']

                # Fetch aliases for the current actor
                aliases_cursor = conn.cursor() # Use a new cursor for this sub-query
                aliases_cursor.execute("SELECT alias_name FROM actor_aliases WHERE actor_id = ? ORDER BY alias_name COLLATE NOCASE", (actor_id,))
                aliases_rows = aliases_cursor.fetchall()
                aliases = [alias_row['alias_name'] for alias_row in aliases_rows]

                actors_data.append({
                    'id': actor_id,
                    'name': actor_name,
                    'aliases': aliases
                })
        return actors_data
    except sqlite3.Error as e:
        print(f"Database error while fetching all actors with aliases: {e}")
        return [] # Return empty list on error
    except Exception as e:
        print(f"An unexpected error occurred in get_all_actors_with_aliases: {e}")
        return []


if __name__ == '__main__':
    print(f"Using database: {DEFAULT_DB_PATH}")
    if not os.path.exists(DEFAULT_DB_PATH):
        print(f"Database file {DEFAULT_DB_PATH} does not exist. Please run database_setup.py first.")
    else:
        # 1. Add a new actor
        print("\n--- Adding New Actor ---")
        actor1_name = "Test Actor One"
        actor1_id = add_actor(DEFAULT_DB_PATH, actor1_name)
        if actor1_id is not None:
            print(f"Successfully processed '{actor1_name}', ID: {actor1_id}")

        actor2_name = "Another Test Star"
        actor2_id = add_actor(DEFAULT_DB_PATH, actor2_name)
        if actor2_id is not None:
            print(f"Successfully processed '{actor2_name}', ID: {actor2_id}")

        # Try adding existing actor
        print("\n--- Adding Existing Actor ---")
        existing_actor_id = add_actor(DEFAULT_DB_PATH, actor1_name) # Should return existing ID
        if existing_actor_id is not None:
             print(f"Attempt to add existing actor '{actor1_name}' again, ID: {existing_actor_id}")


        # 2. Add aliases
        print("\n--- Adding Aliases ---")
        if actor1_id is not None:
            add_alias(DEFAULT_DB_PATH, actor1_id, "TAO")
            add_alias(DEFAULT_DB_PATH, actor1_id, "TestAlias1")
            add_alias(DEFAULT_DB_PATH, actor1_id, "TAO") # Try adding existing alias for same actor

        if actor2_id is not None:
            add_alias(DEFAULT_DB_PATH, actor2_id, "ATS")
            add_alias(DEFAULT_DB_PATH, actor2_id, "AnotherATS")
            # Try adding an alias that might exist for actor1
            add_alias(DEFAULT_DB_PATH, actor2_id, "TAO") # Should fail if TAO is unique globally

        # Try adding alias for non-existent actor
        print("\n--- Adding Alias for Non-existent Actor ---")
        add_alias(DEFAULT_DB_PATH, 9999, "NonExistentActorAlias")


        # 3. Get actor ID by name or alias
        print("\n--- Getting Actor ID by Name/Alias ---")
        name_to_find = actor1_name
        found_id = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, name_to_find)
        print(f"Searching for '{name_to_find}', Found ID: {found_id}")

        alias_to_find = "TAO"
        found_id_by_alias = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, alias_to_find)
        print(f"Searching for alias '{alias_to_find}', Found ID: {found_id_by_alias}")

        alias_to_find_other_actor = "ATS"
        found_id_by_alias_other = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, alias_to_find_other_actor)
        print(f"Searching for alias '{alias_to_find_other_actor}', Found ID: {found_id_by_alias_other}")

        non_existent_name = "Totally Unknown Person"
        found_id_non_existent = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, non_existent_name)
        print(f"Searching for '{non_existent_name}', Found ID: {found_id_non_existent}")


        # 4. Get aliases for an actor
        print("\n--- Getting Aliases for Actor ---")
        if actor1_id is not None:
            aliases1 = get_aliases_for_actor(DEFAULT_DB_PATH, actor1_id)
            print(f"Aliases for actor ID {actor1_id} ({actor1_name}): {aliases1}")

        if actor2_id is not None:
            aliases2 = get_aliases_for_actor(DEFAULT_DB_PATH, actor2_id)
            print(f"Aliases for actor ID {actor2_id} ({actor2_name}): {aliases2}")

        aliases_non_existent = get_aliases_for_actor(DEFAULT_DB_PATH, 9999)
        print(f"Aliases for non-existent actor ID 9999: {aliases_non_existent}")

        # Demonstrate pre-existing data from database_setup.py
        print("\n--- Testing with pre-existing data ---")
        john_doe_id = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, "John Doe")
        if john_doe_id:
            print(f"John Doe's ID: {john_doe_id}")
            aliases_jd = get_aliases_for_actor(DEFAULT_DB_PATH, john_doe_id)
            print(f"John Doe's aliases: {aliases_jd}")
            # Try adding an existing alias for John Doe
            add_alias(DEFAULT_DB_PATH, john_doe_id, "Johnny D")

        j_doe_id = get_actor_id_by_name_or_alias(DEFAULT_DB_PATH, "J. Doe")
        if j_doe_id:
             print(f"Actor ID for 'J. Doe' (alias of John Doe): {j_doe_id}")

        # Test get_actor_name_by_id
        print("\n--- Getting Actor Name by ID ---")
        if actor1_id:
            name = get_actor_name_by_id(DEFAULT_DB_PATH, actor1_id)
            print(f"Name for actor ID {actor1_id}: {name}")
        if john_doe_id:
            name = get_actor_name_by_id(DEFAULT_DB_PATH, john_doe_id)
            print(f"Name for actor ID {john_doe_id} (John Doe): {name}")

        name_non_existent = get_actor_name_by_id(DEFAULT_DB_PATH, 9999)
        print(f"Name for non-existent actor ID 9999: {name_non_existent}")


        print("\n--- End of Tests ---")

        # Test get_all_actors_with_aliases
        print("\n--- Getting All Actors with Aliases ---")
        all_actors_data = get_all_actors_with_aliases(DEFAULT_DB_PATH)
        if all_actors_data:
            print(f"Found {len(all_actors_data)} actors:")
            for ad in all_actors_data:
                print(f"  ID: {ad['id']}, Name: {ad['name']}, Aliases: {ad['aliases']}")
        else:
            print("No actors found or error fetching all actors.")