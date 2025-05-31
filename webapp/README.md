# Web Application (Flask)

This directory contains the Flask web application for the Video Classification Management System.

## Running the Basic App

There are a couple of ways to run this basic Flask application:

**1. Using `python app.py` (Development Server):**

   Navigate to the `webapp` directory and run the `app.py` script directly:
   ```bash
   cd webapp
   python app.py
   ```
   This will start Flask's built-in development server, typically on `http://127.0.0.1:5000/`. The `debug=True` flag is set, which is useful for development (auto-reloads on code changes, provides debugger).

**2. Using the `flask` command-line interface:**

   You need to tell Flask where your application is by setting the `FLASK_APP` environment variable. From the **project root directory**:

   ```bash
   # For Linux/macOS
   export FLASK_APP=webapp/app.py
   flask run

   # For Windows (cmd.exe)
   set FLASK_APP=webapp/app.py
   flask run

   # For Windows (PowerShell)
   $env:FLASK_APP = "webapp/app.py"
   flask run
   ```
   This also starts the development server. If you want to enable debug mode with this method, you can set `FLASK_DEBUG=1` (or `FLASK_ENV=development` for older Flask versions).

   ```bash
   # Example with debug mode
   export FLASK_APP=webapp/app.py
   export FLASK_DEBUG=1
   flask run
   ```

The application will be accessible at `http://127.0.0.1:5000/` in your web browser. You should see "Hello, Flask World!".

---

*Further instructions will be added here as the web application is developed (e.g., installing dependencies from `requirements.txt`, database interactions, specific routes).*
```
