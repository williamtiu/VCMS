"""
main.py: Command-Line Interface for the Video Classification Management System.

Provides functionalities for:
- Setting up and initializing the database.
- Adding actors and aliases.
- Processing video files in a directory to extract and store metadata,
  optionally using AI for metadata enhancement.
"""
import argparse
import os
import sys
import json
import logging
from typing import Optional, List, Any, Tuple, Dict

# For direct execution of main.py from project root:
# Ensure project root is in sys.path to allow finding 'backend', 'ai_models',
# 'database' packages. This is for convenience when running `python main.py ...`.
# If main.py is installed as part of a package, this might not be necessary.
_MAIN_PY_DIR = os.path.dirname(os.path.abspath(__file__))
if _MAIN_PY_DIR not in sys.path:  # Should be project root if main.py is at root
    sys.path.insert(0, _MAIN_PY_DIR)

# Import project modules after path adjustment
from backend.metadata_processor import process_video_file
from backend.actor_management import add_actor, add_alias
from ai_models.llm_analyzer import configure_ollama_client

# --- Global Configuration & Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_DB_RELATIVE_PATH: str = os.path.join("database", "video_management.db")
VIDEO_EXTENSIONS: Tuple[str, ...] = (".mp4", ".avi", ".mkv", ".mov", ".webm")


# --- Helper Functions for CLI Actions ---
def _ensure_db_directory_exists(db_path: str) -> None:
    """
    Ensures the directory for the SQLite database file exists.

    Args:
        db_path (str): The full path to the database file.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        except OSError as e:
            logger.error(
                f"Failed to create database directory {db_dir}: {e}", exc_info=True
            )


def _handle_db_setup(db_path_to_setup: str) -> bool:
    """
    Handles the database setup process by creating tables and inserting sample data.

    Args:
        db_path_to_setup (str): The path to the database file to set up.

    Returns:
        bool: True if setup was successful, False otherwise.
    """
    logger.info(f"Initiating database setup for: {db_path_to_setup}")
    _ensure_db_directory_exists(db_path_to_setup)

    try:
        from database.database_setup import (
            create_connection as setup_create_conn,
            create_all_tables,
            insert_sample_data,
        )

        conn = setup_create_conn(db_path_to_setup)
        if not conn:
            logger.error(
                f"Failed to create database connection to '{db_path_to_setup}' for setup."
            )
            return False

        try:
            if not create_all_tables(conn):
                logger.error("Database setup failed: Not all tables could be created.")
                return False
            if not insert_sample_data(conn):
                logger.warning(
                    "There were issues during sample data insertion. Check logs."
                )
            conn.commit()
            logger.info(
                "Database setup and sample data insertion completed successfully."
            )
            return True
        except Exception as e:
            logger.error(
                f"Error during table creation or sample data insertion: {e}",
                exc_info=True,
            )
            conn.rollback()
            return False
        finally:
            conn.close()

    except ImportError:
        logger.error(
            "Failed to import database setup functions. Ensure 'database.database_setup.py' is accessible.",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during database setup: {e}", exc_info=True
        )
        return False


def _handle_add_actor(args_ns: argparse.Namespace, default_db_path: str) -> None:
    """
    Handles the --add_actor CLI command.

    Args:
        args_ns (argparse.Namespace): The parsed command-line arguments.
        default_db_path (str): The default database path to use if not specified in args.
    """
    if not args_ns.add_actor or len(args_ns.add_actor) == 0:
        logger.warning("No actor name provided for --add_actor.")
        return

    actor_name: str = args_ns.add_actor[0]
    cmd_db_path: str = default_db_path
    if len(args_ns.add_actor) > 1:
        cmd_db_path = os.path.abspath(args_ns.add_actor[1])
        _ensure_db_directory_exists(cmd_db_path)

    logger.info(f"Attempting to add actor '{actor_name}' to database: {cmd_db_path}")
    actor_id = add_actor(cmd_db_path, actor_name)
    if actor_id is None and actor_name.strip():
        logger.error(f"Failed to add or retrieve actor '{actor_name}'.")


def _handle_add_alias(args_ns: argparse.Namespace, default_db_path: str) -> None:
    """
    Handles the --add_alias CLI command.

    Args:
        args_ns (argparse.Namespace): The parsed command-line arguments.
        default_db_path (str): The default database path to use if not specified in args.
    """
    if not args_ns.add_alias or len(args_ns.add_alias) < 2:
        logger.error(
            "--add_alias requires ACTOR_ID and ALIAS_NAME. Optional [DB_PATH]."
        )
        return

    actor_id_str: str = args_ns.add_alias[0]
    alias_name: str = args_ns.add_alias[1]
    cmd_db_path: str = default_db_path
    if len(args_ns.add_alias) > 2:
        cmd_db_path = os.path.abspath(args_ns.add_alias[2])
        _ensure_db_directory_exists(cmd_db_path)

    try:
        actor_id: int = int(actor_id_str)
        logger.info(
            f"Attempting to add alias '{alias_name}' for actor ID {actor_id} to database: {cmd_db_path}"
        )
        if not add_alias(cmd_db_path, actor_id, alias_name):
            logger.warning(
                f"Call to add_alias for '{alias_name}' (Actor ID: {actor_id}) returned False. See previous logs for details."
            )
    except ValueError:
        logger.error(f"Actor ID '{actor_id_str}' must be an integer.", exc_info=True)


def _handle_process_videos(
    args_ns: argparse.Namespace, default_db_path: str
) -> None:
    """
    Handles video processing from the --video_dir CLI command.

    Args:
        args_ns (argparse.Namespace): The parsed command-line arguments.
        default_db_path (str): The default database path to use.
    """
    video_dir: str = args_ns.video_dir
    if not os.path.isdir(video_dir):
        logger.error(
            f"Video directory '{video_dir}' not found or is not a directory."
        )
        sys.exit(1)

    logger.info(f"Processing videos in directory: {video_dir}")
    logger.info(f"Using database: {default_db_path}")

    _ensure_db_directory_exists(default_db_path)

    found_videos: int = 0
    processed_successfully: int = 0

    for filename in os.listdir(video_dir):
        if filename.lower().endswith(VIDEO_EXTENSIONS):
            found_videos += 1
            filepath: str = os.path.join(video_dir, filename)
            logger.info(f"\n--- Processing file: {filepath} ---")
            try:
                result: Optional[Dict[str, Any]] = process_video_file(
                    filepath, default_db_path
                )
                if result and "consolidated_metadata" in result:
                    # Direct output for user
                    print(json.dumps(result["consolidated_metadata"], indent=4))
                    processed_successfully += 1
                else:
                    logger.warning(
                        f"No result or error processing {filepath}. See previous logs."
                    )
            except Exception as e:
                logger.error(
                    f"Critical error processing {filepath}: {e}", exc_info=True
                )
            logger.info("-" * 50)
        else:
            logger.debug(f"Skipping non-video file: {filename}")

    if found_videos == 0:
        logger.info(
            f"No video files found in '{video_dir}' with extensions: {VIDEO_EXTENSIONS}."
        )
    else:
        logger.info(
            f"Processed {processed_successfully}/{found_videos} video files found in '{video_dir}'."
        )


# --- Main CLI Function ---
def main() -> None:
    """
    Main function for the CLI application. Parses arguments and calls appropriate handlers.
    """
    logger.info("CLI application started.")

    parser = argparse.ArgumentParser(
        description="Video Classification Management System CLI",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--video_dir",
        type=str,
        help="Path to the directory containing video files to process.",
    )
    parser.add_argument(
        "--db_path",
        type=str,
        help=f"Path to the SQLite database file.\n(default: {DEFAULT_DB_RELATIVE_PATH})",
    )
    parser.add_argument(
        "--setup_db",
        action="store_true",
        help=(
            "If provided, run database_setup.py logic to initialize/reset the DB.\n"
            "This will use the path from --db_path or the default."
        ),
    )
    parser.add_argument(
        "--add_actor",
        nargs="+",
        metavar="ACTOR_NAME [DB_PATH]",
        help=(
            "Add a new actor. Provide actor name.\n"
            "Optionally, provide a specific DB_PATH for this operation.\n"
            'Example: --add_actor "New Actor" [path/to/your.db]'
        ),
    )
    parser.add_argument(
        "--add_alias",
        nargs="+",
        metavar="ACTOR_ID ALIAS_NAME [DB_PATH]",
        help=(
            "Add an alias for an actor. Provide ACTOR_ID and ALIAS_NAME.\n"
            "Optionally, provide a specific DB_PATH.\n"
            'Example: --add_alias 1 "N. Actor" [path/to/your.db]'
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,
        help="Enable verbose DEBUG logging output.",
    )

    args = parser.parse_args()

    logging.getLogger().setLevel(args.loglevel)
    logger.info(f"Log level set to: {logging.getLevelName(args.loglevel)}")

    effective_db_path: str = os.path.abspath(
        args.db_path if args.db_path else DEFAULT_DB_RELATIVE_PATH
    )
    logger.info(f"Effective database path: {effective_db_path}")

    logger.info("Attempting to configure Ollama client (AI features)...")
    if configure_ollama_client():
        logger.info("Ollama client configured successfully (or was already configured).")
    else:
        logger.warning(
            "Ollama client could not be configured. AI enhancement features may be limited or unavailable."
        )

    action_taken: bool = False
    if args.setup_db:
        action_taken = True
        if not _handle_db_setup(effective_db_path):
            logger.critical("Database setup failed. Exiting application.")
            sys.exit(1)

    if args.add_actor:
        action_taken = True
        _handle_add_actor(args, effective_db_path)

    if args.add_alias:
        action_taken = True
        _handle_add_alias(args, effective_db_path)

    if args.video_dir:
        action_taken = True
        _handle_process_videos(args, effective_db_path)

    if not action_taken:
        logger.info("No specific action requested. Use -h or --help for usage information.")
        parser.print_help()

    logger.info("CLI application finished.")


if __name__ == "__main__":
    main()
```
