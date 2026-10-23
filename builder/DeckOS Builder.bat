@echo off
rem DeckOS Builder for Windows. First run sets up a private Python environment (~150 MB)
rem in builder\.venv next to this file.
setlocal
set "VENV=%~dp0.venv"
if not exist "%VENV%\Scripts\pythonw.exe" (
  echo Setting up DeckOS Builder ^(first run only^)...
  python -m venv "%VENV%" || (echo Python 3.11+ is required: winget install Python.Python.3.12 & pause & exit /b 1)
  "%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
  "%VENV%\Scripts\python.exe" -m pip install --quiet PySide6-Essentials || (echo Could not install PySide6 & pause & exit /b 1)
)
start "" "%VENV%\Scripts\pythonw.exe" "%~dp0deckos_builder.py"
