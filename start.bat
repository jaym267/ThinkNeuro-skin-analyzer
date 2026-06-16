@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting DermAI Pro...
echo.
echo Once the app loads, your browser will open automatically.
echo Press CTRL+C to stop the app.
echo.
set PYTHONUTF8=1
py -m streamlit run app.py --server.port 8501
pause
