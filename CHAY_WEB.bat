@echo off
cd /d "%~dp0PythonApplication1"
if exist "..\.venv\Scripts\python.exe" (
    ..\.venv\Scripts\python.exe web_app.py
) else if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe web_app.py
) else (
    python web_app.py
)
pause
