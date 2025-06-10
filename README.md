# Video Classification Management System

This project is a Video Classification Management System designed to organize, classify, and manage a collection of video files. It will feature a Python backend, AI-powered metadata enhancement, a SQLite database for storage, and a Flask web application for user interaction.

## Project Goals

*   **Organization:** Store and manage video files with associated metadata.
*   **Classification:** Automatically extract and suggest metadata (title, actors, publisher, etc.) from filenames and video content.
*   **AI Enhancement:** Utilize AI models (e.g., LLMs) to enhance video descriptions, suggest tags, and potentially analyze video content.
*   **User Interface:** Provide a web-based interface for uploading videos, viewing metadata, and managing the video library.
*   **Search & Filtering:** Allow users to search and filter videos based on various criteria.

## Directory Structure

*   **/backend:** Contains the core Python logic for video processing, metadata extraction, database interactions, and AI model interfacing.
*   **/frontend:** (Initially planned, now integrated into /webapp) Would have contained frontend specific code if a separate SPA was built.
*   **/webapp:** Contains the Flask web application, including HTML templates, static assets (CSS, JS), and Flask route definitions.
*   **/database:** Holds database-related scripts, including schema definition, setup scripts, and the SQLite database file itself.
*   **/ai_models:** Contains scripts and modules related to AI model integration, such_as functions for interacting with LLMs or other content analysis tools.
*   **/tests:** Includes unit tests and integration tests for the various components of the system.
*   **/data:**
    *   **/data/videos:** Intended for storing sample video files for testing and development.
    *   **/data/uploads:** Default directory for videos uploaded via the web application.
*   **main.py:** The main entry point for the application (primarily for CLI operations or initial setup).
*   **README.md:** This file, providing an overview of the project.
*   **requirements.txt:** Lists the Python dependencies for the project.
*   **config.py:** (Potentially, or integrated into webapp/config.py) For application-level configurations.
