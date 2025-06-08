# AI Models Setup & Overview

This document outlines the setup and functionality of the AI models used in the Video Classification Management System. These models leverage local Large Language Models (LLMs) via Ollama and network search capabilities to enhance video metadata.

## 1. Core AI Modules

The AI capabilities are primarily delivered through the following Python modules located in the `ai_models/` directory:

### a. Ollama Interaction (`llm_analyzer.py`)
- **Purpose:** Connects to a locally running Ollama instance to leverage LLMs for text analysis.
- **Key Functions:**
    - `configure_ollama_client(host)`: Initializes the connection to the Ollama server. This should ideally be called once at application startup (e.g., in `webapp/app.py` or `main.py`). It's also called on module load in `content_analysis.py` and within `llm_analyzer.py` itself if the client is not configured before a call.
    - `analyze_text_with_llm(text_to_analyze, task_description, model)`: Sends text to the LLM with a specific task (e.g., suggest a title, extract actor names, identify publisher).
- **Configuration:**
    - `DEFAULT_OLLAMA_MODEL` (default: 'llama3'): Specifies the default Ollama model to use. Ensure this model is pulled in your Ollama instance.
    - `DEFAULT_OLLAMA_HOST` (default: 'http://localhost:11434'): The API endpoint for your Ollama server.

### b. Network Search (`network_search.py`)
- **Purpose:** Performs web searches to find supplementary information and fetches content from URLs.
- **Key Functions:**
    - `search_web(query, max_results)`: Uses DuckDuckGo to search the web for the given query.
    - `fetch_url_content(url, timeout)`: Fetches and parses textual content from a given webpage URL.
- **Dependencies:** Uses `duckduckgo_search` for web searches (no API key needed), `requests` for HTTP requests, and `BeautifulSoup4` for HTML parsing.

### c. Content Analysis Orchestrator (`content_analysis.py`)
- **Purpose:** Acts as the central hub for AI-driven metadata extraction. It uses `llm_analyzer.py` and `network_search.py` to process textual information.
- **Key Functions:**
    - `enhance_textual_metadata(text_input, original_filename)`: Takes textual input (derived from filename parsing or future OCR/STT) and uses LLM and network search to:
        - Suggest video titles.
        - Identify potential actors and publishers.
        - Find related information online for identified entities.
    - `analyze_transcribed_audio(transcribed_text)`: (Currently focused on name extraction) Analyzes text (presumed to be from audio transcription) to extract mentioned names using the LLM.
- **Graceful Degradation:** If the Ollama server is not available or configured, LLM-dependent enhancements will be skipped, and the module will log appropriate warnings. Network search may also be limited if it relies on initial LLM output.

## 2. Setup Instructions

### a. Ollama (Local LLM)
You need to have Ollama installed and running with a suitable model.

1.  **Install Ollama:** Follow the official instructions at [https://ollama.com/](https://ollama.com/).
2.  **Download a Model:** Once Ollama is running, pull a model. The system defaults to `llama3`.
    ```bash
    ollama pull llama3
    ```
    You can use other models (e.g., `phi3`, `mistral`), but you might need to adjust `DEFAULT_OLLAMA_MODEL` in `llm_analyzer.py` or ensure your application configures it.
3.  **Ensure Ollama is Serving:** By default, Ollama serves on `http://localhost:11434`. The application will attempt to connect to this address.

### b. Python Environment & Dependencies
Ensure you have a Python environment (e.g., venv) set up and all project dependencies installed from the main `requirements.txt` file:
```bash
# From the project root directory
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
The `requirements.txt` file includes `ollama`, `duckduckgo_search`, `requests`, and `beautifulsoup4` among other project dependencies.

## 3. Usage in the System
The AI content analysis features are integrated into the video processing pipeline (`backend/metadata_processor.py`). When a video is processed, if the initial filename parsing yields incomplete data, the system will attempt to use these AI modules to enhance the metadata. The results, including AI suggestions and network search findings, will be visible in the web UI's results display page.
```
