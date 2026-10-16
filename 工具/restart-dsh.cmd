@echo off
REM ===========================================================================
REM  restart-dsh.cmd -- restart DeepSeek Harness so the new sidebar tabs load.
REM
REM  *** THIS FILE MUST CONTAIN ZERO NON-ASCII BYTES. ***
REM  cmd.exe parses .cmd in the OEM codepage. One Chinese character here splits
REM  the file into half a command. AGENTS.md 0.05; failed 7 times, most recently
REM  at 00:53 today with this very script (it had the words for port 8794 and a
REM  Chinese log filename inline, and cmd.exe could not run it at all).
REM  Check before running:
REM      $b=[IO.File]::ReadAllBytes($p); ($b | ? {$_ -gt 127}).Count   # must be 0
REM
REM  Chinese paths live in _boot_8794.py, never on a command line here.
REM
REM  Why the 20s delay: this script is launched from inside the running DSH turn.
REM  Killing DSH immediately would kill the turn that started it, and the user
REM  would see "this turn failed" instead of a restart.
REM ===========================================================================

setlocal
set EXE=D:\deepseek_HARNESS_guanfangban\DeepSeek Harness.exe
set PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe
set WS=D:\DSHworkspace
set LOG=D:\DSHworkspace\_restart_dsh.log

echo [%DATE% %TIME%] restart-dsh.cmd started >> "%LOG%"

REM ---- 1. bring up the page the second sidebar tab points at -----------------
echo [%DATE% %TIME%] starting port 8794 if needed >> "%LOG%"
"%PY%" -X utf8 "%WS%\_boot_8794.py" >> "%LOG%" 2>&1

echo [%DATE% %TIME%] waiting 20s so the current turn can finish >> "%LOG%"
timeout /t 20 /nobreak >nul

REM ---- 2. restart DSH ------------------------------------------------------
echo [%DATE% %TIME%] killing DeepSeek Harness >> "%LOG%"
taskkill /IM "DeepSeek Harness.exe" /F >> "%LOG%" 2>&1

echo [%DATE% %TIME%] waiting for ports to free >> "%LOG%"
timeout /t 8 /nobreak >nul

if not exist "%EXE%" (
  echo [%DATE% %TIME%] ERROR exe not found >> "%LOG%"
  exit /b 1
)

echo [%DATE% %TIME%] relaunching >> "%LOG%"
start "" "%EXE%"

echo [%DATE% %TIME%] done >> "%LOG%"
endlocal
