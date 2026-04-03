@echo off
echo.
echo  RepurposeAI - Drug Repurposing Intelligence Platform
echo  =====================================================
echo.

if not exist venv (
    echo  Creating virtual environment...
    python -m venv venv
)

echo  Activating virtual environment...
call venv\Scripts\activate.bat

echo  Installing dependencies...
pip install -r requirements.txt -q

echo.
echo  Starting server at http://localhost:5000
echo  Open your browser and go to: http://localhost:5000
echo  Press Ctrl+C to stop
echo.

cd backend
set OPENROUTER_API_KEY=
for /f "tokens=2 delims==" %%a in ('findstr "OPENROUTER_API_KEY" ..\.env 2^>nul') do set OPENROUTER_API_KEY=%%a

if "%OPENROUTER_API_KEY%"=="" (
    echo  WARNING: No API key found in .env file
    echo  Add your key: OPENROUTER_API_KEY=sk-or-v1-...
    echo.
)

python app.py
pause
