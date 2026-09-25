@echo off
cd /d "%~dp0"
echo.
echo Starting PocketSmart AI...
echo Open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" app.py
pause
