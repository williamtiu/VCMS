# AI Models Setup

This document outlines the setup for the AI models used in the Video Classification Management System, including local LLM interaction with Ollama and network search capabilities.

## 1. Ollama (Local LLM)

You need to have Ollama installed and running with a suitable model.

1.  **Install Ollama:** Follow the official instructions at [https://ollama.com/](https://ollama.com/).
2.  **Download a Model:** Once Ollama is running, pull a model. For example, to get Llama 3:
    ```bash
    ollama pull llama3
    ```
    Other models like `phi3` or `mistral` can also be used. Note the model name you intend to use, as it will be needed for configuration.
3.  **Ensure Ollama is Serving:** By default, Ollama serves on `http://localhost:11434`. The application will attempt to connect to this address.

## 2. Network Search Dependencies

The Python libraries `duckduckgo_search`, `beautifulsoup4`, and `requests` are used for network search and web content fetching. These will be installed via `requirements.txt`. No special API keys are required for the basic search functionality with DuckDuckGo.

## 3. Python Environment

Ensure you have a Python environment (e.g., venv) set up and the dependencies installed:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
```
