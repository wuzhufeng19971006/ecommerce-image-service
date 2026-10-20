@echo off
setlocal
set ROOT=%~dp0
start "Yitu Backend" cmd /k "cd /d %ROOT%backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
start "Yitu Frontend" cmd /k "cd /d %ROOT%frontend && npm.cmd run dev"
endlocal
