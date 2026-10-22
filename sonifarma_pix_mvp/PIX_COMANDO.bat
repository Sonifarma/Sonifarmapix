@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" atualizar.py %*
) else (
  py -3.12 atualizar.py %*
)
exit /b %errorlevel%
