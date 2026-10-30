@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run setup.bat first.
    exit /b 1
)

start "Cropwise API" /D "%~dp0" "%~dp0.venv\Scripts\python.exe" -m uvicorn cropwise.api:app --host 127.0.0.1 --port 8000
"%~dp0.venv\Scripts\python.exe" -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501