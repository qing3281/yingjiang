@echo off
chcp 936 >nul
title 影匠监工台
cd /d "%~dp0"
echo.
echo   影匠监工台
echo   浏览器会自动打开 http://127.0.0.1:8791/
echo   关掉这个窗口就是停掉它。
echo.
"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 -u _监工.py --戏 觉醒 --口 8791
pause
