@echo off
REM Lance l application Second avis (double-clic)
cd /d "%~dp0"
set "PY="
for %%P in (python py python3) do if not defined PY (%%P --version >nul 2>&1 && set "PY=%%P")
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY for /d %%D in ("C:\Program Files\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY for %%F in ("%LOCALAPPDATA%\Microsoft\WindowsApps\python3.1*.exe") do if not defined PY set "PY=%%~fF"
if not defined PY (
  echo.
  echo Python est introuvable. Faites une capture de cet ecran et envoyez-la a Claude.
  echo --- diagnostic ---
  where python
  where py
  dir /b "%LOCALAPPDATA%\Programs\Python" 2>nul
  dir /b "%LOCALAPPDATA%\Microsoft\WindowsApps\python*" 2>nul
  pause
  exit /b
)
echo Python utilise : %PY%
"%PY%" --version
echo Installation des bibliotheques (premiere fois : 1 a 2 minutes)...
"%PY%" -m pip install -q -r requirements.txt
echo Ouverture de l application dans le navigateur...
"%PY%" -m streamlit run app.py
pause
