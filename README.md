# Video Classification Management System

This project is a Python-based video classification management system leveraging AI technologies to automate the organization and classification of video files. It parses filenames, fetches metadata online, manages actor aliases, and uses AI to enhance information for untitled or incomplete video data.

## Features

*   **Filename Parsing:** Extracts code, actor(s), and title from various video filename formats.
*   **Metadata Database:** Stores video metadata (codes, actors, titles, publishers) and actor alias mappings in a SQLite database.
*   **Actor Alias Management:** Allows associating multiple aliases with a single actor identity.
*   **AI-Powered Metadata Enhancement:**
    *   Utilizes a local Large Language Model (LLM) via Ollama (e.g., Llama 3, Phi-3) to:
        *   Suggest titles for videos based on available textual information.
        *   Identify potential actors and publishers from text.
    *   Performs network searches (via DuckDuckGo) to find supplementary information online for identified entities (actors, publishers).
    *   This augments metadata derived from filename parsing, especially for videos with incomplete initial data.
*   **Standardized Filenaming:** Generates standardized filenames based on consolidated metadata.
*   **Command-Line Interface (CLI):** (`main.py`) For processing videos, managing actors, and database setup.
*   **Web Interface (Flask):** (`webapp/`) Provides a user-friendly web UI for:
    *   Uploading videos for processing.
    *   Viewing detailed processing results, including AI-derived suggestions and network search findings.
    *   Managing actors and their aliases.

## Directory Structure

- `ai_models/`: Contains AI modules for LLM interaction (`llm_analyzer.py`), network search (`network_search.py`), and content analysis orchestration (`content_analysis.py`). Includes a `README.md` for AI setup.
- `backend/`: Contains the core server-side logic:
    - `filename_parser.py`: Parses video filenames.
    - `actor_management.py`: Manages actor and alias data.
    - `metadata_processor.py`: Orchestrates the video processing pipeline, including AI enhancement.
    - `database_operations.py`: Handles direct database interactions.
- `database/`: Manages data storage. `video_management.db` is the SQLite database. `database_setup.py` initializes it.
- `data/`:
    - `uploads/`: Default directory for storing videos uploaded via the web interface.
    - `videos/`: (Optional) Can be used for sample videos for CLI processing.
- `tests/`: Includes unit tests for backend modules.
- `webapp/`: Houses the Flask web application:
    - `app.py`: Main Flask application file.
    - `static/`: For CSS, JavaScript.
    - `templates/`: For HTML templates.
- `main.py`: The main entry point for the Command-Line Interface (CLI).
- `requirements.txt`: Lists Python package dependencies.
- `README.md`: This file.

## Getting Started

### 1. Prerequisites
*   Python 3.8 or higher.
*   (Optional but Recommended) A Python virtual environment (`venv`).

### 2. Clone the Repository
```bash
git clone <repository_url>
cd <repository_directory>
```

### 3. Set Up Python Environment & Install Dependencies
```bash
# From the project root directory
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set Up AI Features (Ollama)
For AI-powered metadata enhancement, you need to set up Ollama and download an LLM model:
*   **Install Ollama:** Follow the official instructions at [https://ollama.com/](https://ollama.com/).
*   **Download an LLM Model:** Once Ollama is running, pull a model. The system defaults to `llama3`.
    ```bash
    ollama pull llama3
    ```
    Other models like `phi3` or `mistral` can also be used (see Configuration section).
*   Ensure your Ollama server is running (usually at `http://localhost:11434`) when using AI features.
*   For more details, see `ai_models/README.md`.

### 5. Initialize the Database
You can initialize the database using the CLI:
```bash
python main.py --setup_db
```
This creates `database/video_management.db` and sets up the necessary tables.

## Usage

The system can be primarily interacted with via the Web Interface or the Command-Line Interface.

### a. Web Interface
1.  **Start the Flask Development Server:**
    ```bash
    # From the project root directory
    python webapp/app.py
    ```
    Or, using Flask CLI:
    ```bash
    export FLASK_APP=webapp/app.py # On Linux/macOS
    # set FLASK_APP=webapp\app.py # On Windows cmd.exe
    # $env:FLASK_APP = "webapp/app.py" # On Windows PowerShell
    flask run
    ```
    The web application will typically be available at `http://127.0.0.1:5000`.

2.  **Using the Web UI:**
    *   **Upload Videos:** Navigate to the "Upload Video" page to upload files. The system will process them and display results, including AI-enhanced metadata if applicable.
    *   **Manage Actors:** Use the "Manage Actors" page to view, add actors, and assign aliases.

### b. Command-Line Interface (`main.py`)
The CLI provides functionalities for batch processing and direct database management.

*   **Process a directory of videos:**
    ```bash
    python main.py --video_dir path/to/your/videos/
    ```
*   **Add an actor:**
    ```bash
    python main.py --add_actor "Actor Name"
    ```
*   **Add an alias to an actor (requires Actor ID):**
    ```bash
    python main.py --add_alias <actor_id> "Alias Name"
    ```
Run `python main.py --help` for more CLI options.

**Note on AI Features:** When processing videos (via CLI or Web UI), if filename information is sparse, the system will automatically attempt to use the configured LLM (Ollama) and network search to enhance metadata. For these features to work, ensure Ollama is running with a model and an internet connection is available.

## Configuration

*   **Ollama Model:** The default LLM model used is `llama3`. This can be changed by modifying `DEFAULT_OLLAMA_MODEL` in `ai_models/llm_analyzer.py`.
*   **Ollama Host:** The system connects to Ollama at `http://localhost:11434` by default. This can be changed by modifying `DEFAULT_OLLAMA_HOST` in `ai_models/llm_analyzer.py` or by calling `configure_ollama_client(new_host_address)` within the application if customization is needed.
*   **Database Path:** The default database path is `database/video_management.db` relative to the project root. This is configured in `webapp/app.py` (`DEFAULT_DB_PATH`) for the web app and used by CLI operations.

## Contributing

[Guidelines for contributing to the project will be added here.]

## License

[Information about the project's license will be added here.]
```
