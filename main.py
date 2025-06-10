import argparse
import logging
import os

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration (can be moved to a config file later) ---
DATABASE_PATH = os.path.join("database", "video_management.db")
VIDEO_DATA_DIR = os.path.join("data", "videos")


def main():
    """
    Main function to handle command-line arguments and orchestrate operations.
    """
    parser = argparse.ArgumentParser(
        description="Video Classification Management System CLI"
    )
    parser.add_argument(
        "--setup-db", action="store_true", help="Initialize or reset the database."
    )
    parser.add_argument(
        "--process-videos",
        metavar="VIDEO_DIR",
        type=str,
        help="Process all videos in the specified directory.",
    )
    parser.add_argument(
        "--process-file",
        metavar="FILE_PATH",
        type=str,
        help="Process a single video file.",
    )
    # Add more arguments as needed for other functionalities

    args = parser.parse_args()

    if args.setup_db:
        logging.info("Database setup requested.")
        # Placeholder for database setup call
        # from database.database_setup import initialize_database
        # initialize_database(DATABASE_PATH)
        print(
            "Placeholder: Database setup would be called here."
        )  # Replace with actual call

    elif args.process_videos:
        logging.info(f"Processing videos from directory: {args.process_videos}")
        # Placeholder for processing multiple videos
        # from backend.metadata_processor import process_directory
        # process_directory(args.process_videos, DATABASE_PATH)
        print(
            "Placeholder: Video directory processing would be called here."
        )  # Replace

    elif args.process_file:
        logging.info(f"Processing single video file: {args.process_file}")
        # Placeholder for processing a single file
        # from backend.metadata_processor import process_video_file
        # process_video_file(args.process_file, DATABASE_PATH)
        print(
            "Placeholder: Single video file processing would be called here."
        )  # Replace

    else:
        logging.info(
            "No specific action requested. Use -h or --help for options."
        )
        parser.print_help()


if __name__ == "__main__":
    # Ensure the data directories exist
    if not os.path.exists(VIDEO_DATA_DIR):
        os.makedirs(VIDEO_DATA_DIR)
        logging.info(f"Created directory: {VIDEO_DATA_DIR}")

    # (If webapp is part of this main entry, ensure its upload dir exists too)
    # UPLOAD_FOLDER_WEBAPP = os.path.join("webapp", "uploads") # Example
    # if not os.path.exists(UPLOAD_FOLDER_WEBAPP):
    # os.makedirs(UPLOAD_FOLDER_WEBAPP)
    # logging.info(f"Created directory: {UPLOAD_FOLDER_WEBAPP}")

    main()
