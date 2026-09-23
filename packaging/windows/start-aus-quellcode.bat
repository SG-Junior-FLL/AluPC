@echo off
rem AluPC unter Windows direkt aus dem Quellcode starten (Python 3.10+ muss installiert sein).
cd /d "%~dp0\..\.."
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -e .
)
start "" .venv\Scripts\pythonw.exe -m alupc
