@echo off
cd /d "%~dp0PythonApplication1"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe main.py
) else (
    python main.py
)
