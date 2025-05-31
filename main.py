import argparse
import os
import sys
import json
import subprocess # For running database_setup.py

# Adjust sys.path to allow imports from subdirectories if main.py is in the project root
# This ensures that 'backend' and 'ai_models' can be found.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Assuming database_setup.py has a main() function or can be run directly.
# If database_setup.py is refactored to have an importable main function:
# from database.database_setup import main as setup_db_main

# Import functions from our project modules
from backend.metadata_processor import process_video_file
from backend.actor_management import add_actor, add_alias

DEFAULT_DB_RELATIVE_PATH = os.path.join("database", "video_management.db")

def run_db_setup_script():
    """Runs the database_setup.py script."""
    db_setup_script_path = os.path.join('database', 'database_setup.py')
    try:
        print(f"Running database setup script: {db_setup_script_path}...")
        subprocess.run(['python', db_setup_script_path], check=True, capture_output=True, text=True)
        print("Database setup script completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during database setup script execution: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Error: Database setup script not found at {db_setup_script_path}.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Video Classification Management System CLI")

    # Arguments
    parser.add_argument('--video_dir', type=str, help="Path to the directory containing video files to process.")
    parser.add_argument('--db_path', type=str, help=f"Path to the SQLite database file (default: {DEFAULT_DB_RELATIVE_PATH}).")
    parser.add_argument('--setup_db', action='store_true', help="If provided, run database_setup.py to initialize/reset the DB.")

    parser.add_argument('--add_actor', nargs='+', metavar='ACTOR_NAME [DB_PATH]', help='Add a new actor. Example: --add_actor "New Actor" [database/video_management.db]')
    parser.add_argument('--add_alias', nargs='+', metavar='ACTOR_ID ALIAS_NAME [DB_PATH]', help='Add an alias. Example: --add_alias 1 "N. Actor" [database/video_management.db]')

    args = parser.parse_args()

    effective_db_path = args.db_path if args.db_path else os.path.abspath(DEFAULT_DB_RELATIVE_PATH)

    db_dir = os.path.dirname(effective_db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"Created database directory: {db_dir}")

    if args.setup_db:
        if not run_db_setup_script():
            print("Database setup failed. Exiting.")
            return

    if args.add_actor:
        actor_name = args.add_actor[0]
        cmd_db_path = effective_db_path
        if len(args.add_actor) > 1:
            cmd_db_path = args.add_actor[1]
            db_dir_cmd = os.path.dirname(cmd_db_path)
            if db_dir_cmd and not os.path.exists(db_dir_cmd):
                os.makedirs(db_dir_cmd, exist_ok=True)

        print(f"Attempting to add actor '{actor_name}' to database: {cmd_db_path}")
        actor_id = add_actor(cmd_db_path, actor_name)
        # add_actor function already prints messages.
        if actor_id is None: # Explicitly state failure if not covered by add_actor
             print(f"Failed to add or retrieve actor '{actor_name}'.")


    if args.add_alias:
        if len(args.add_alias) < 2:
            parser.error("--add_alias requires ACTOR_ID and ALIAS_NAME, [DB_PATH] is optional.")

        actor_id_str = args.add_alias[0]
        alias_name = args.add_alias[1]
        cmd_db_path = effective_db_path
        if len(args.add_alias) > 2:
            cmd_db_path = args.add_alias[2]
            db_dir_cmd = os.path.dirname(cmd_db_path)
            if db_dir_cmd and not os.path.exists(db_dir_cmd):
                os.makedirs(db_dir_cmd, exist_ok=True)
        try:
            actor_id = int(actor_id_str)
            print(f"Attempting to add alias '{alias_name}' for actor ID {actor_id} to database: {cmd_db_path}")
            if not add_alias(cmd_db_path, actor_id, alias_name):
                 # add_alias function already prints messages for most cases.
                 # This is for cases where it returns False without printing (e.g. empty alias name)
                 print(f"Failed to add alias '{alias_name}' for actor ID {actor_id}.")
        except ValueError:
            print(f"Error: Actor ID '{actor_id_str}' must be an integer.")

    if args.video_dir:
        if not os.path.isdir(args.video_dir):
            print(f"Error: Video directory '{args.video_dir}' not found.")
        else:
            print(f"\nProcessing videos in directory: {args.video_dir}")
            print(f"Using database: {effective_db_path}")
            video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.webm')
            found_videos = 0
            for filename in os.listdir(args.video_dir):
                if filename.lower().endswith(video_extensions):
                    found_videos += 1
                    filepath = os.path.join(args.video_dir, filename)

                    result = process_video_file(filepath, effective_db_path)
                    if result and "consolidated_metadata" in result:
                        print(f"\n--- Results for: {filename} ---")
                        print(json.dumps(result["consolidated_metadata"], indent=4))
                    else:
                        print(f"No result or error processing {filepath}")
                    print("-" * 40)
                else:
                    print(f"Skipping non-video file: {filename}")

            if found_videos == 0:
                print(f"No video files found in '{args.video_dir}'.")

    if not (args.video_dir or args.setup_db or args.add_actor or args.add_alias):
        print("No action requested. Use -h or --help for usage information.")

if __name__ == "__main__":
    main()
