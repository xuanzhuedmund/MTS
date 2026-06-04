@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0"

set "PYTHONPATH=%PROJECT_ROOT%linien-common;%PROJECT_ROOT%linien-client"

echo PYTHONPATH: %PYTHONPATH%

python run_client.py


pause
endlocal