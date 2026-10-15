@echo off
chcp 65001 >nul
title YingJiang Console
rem ---------------------------------------------------------------------
rem ASCII only on purpose. cmd.exe parses .cmd files in the OEM codepage,
rem and Chinese characters here once broke this launcher itself into stray
rem "'xx' is not recognized as an internal or external command" lines.
rem All real logic lives in _console-launch.ps1 (PowerShell reads UTF-8 BOM).
rem
rem Double-clicking this: health-checks port 8791, replaces a STALE console
rem (one built before /api/comfy existed) when nothing is running, starts the
rem fresh _??.py, waits for the port, then opens the browser.
rem ---------------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\_console-launch.ps1"
exit /b 0