@echo off
cd /d "%~dp0"

REM 古いPythonだと依存パッケージのインストールに失敗するため、新しいバージョンを優先的に探し、
REM 3.9未満しか見つからない場合ははっきりエラーにする。
set PYTHON_CMD=

call :try_py_version 3.13
call :try_py_version 3.12
call :try_py_version 3.11
call :try_py_version 3.10
call :try_py_version 3.9
if defined PYTHON_CMD goto :python_found

py -3 -c "import sys; exit(0 if sys.version_info[:2] >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 (
  set PYTHON_CMD=py -3
  goto :python_found
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -c "import sys; exit(0 if sys.version_info[:2] >= (3, 9) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :python_found
  )
)

echo Python 3.9 or newer was not found.
echo Please install Python 3 from https://www.python.org/downloads/
pause
exit /b 1

:try_py_version
if defined PYTHON_CMD exit /b 0
py -%1 -c "exit(0)" >nul 2>nul
if not errorlevel 1 set PYTHON_CMD=py -%1
exit /b 0

:python_found
if not exist ".venv" (
  echo First-time setup is running (this can take a few minutes)...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    pause
    exit /b 1
  )
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

if not exist "data\tours.db" (
  echo Preparing master data (sample tours, unit prices, etc.)...
  set PYTHONPATH=src
  python -m tlst_automation.seed
)

if not exist "C:\Program Files\LibreOffice\program\soffice.exe" (
  echo LibreOffice was not found. It is required for PDF export.
  echo   https://www.libreoffice.org/download/download/
  echo Excel/PowerPoint generation still works without it.
)

set PYTHONPATH=src
streamlit run tour_portal_app.py
pause
