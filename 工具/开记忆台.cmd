@echo off
chcp 65001 >nul
title 记忆监工台
cd /d D:\DSHworkspace
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo.
echo   记忆监工台正在起，好了会打印网址
echo   看完直接关这个黑窗口就停了
echo.
D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe -X utf8 _记忆台.py
pause