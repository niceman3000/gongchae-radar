@echo off
cd /d "%~dp0"
rem dev only: reload app/src code on every run (see streamlit_app.py). Not set on the deploy server.
set GONGCHAE_DEV=1
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.headless true
pause
