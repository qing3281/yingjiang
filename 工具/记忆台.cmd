@echo off
chcp 65001 >nul
title 记忆台
cd /d D:\DSHworkspace
"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 -u _开台.py 记忆
if errorlevel 1 pause
