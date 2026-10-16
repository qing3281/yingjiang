@echo off
cd /d "E:\Ó°½³AI\ComfyUI"
"E:\Ó°½³AI\ComfyUI\.venv\Scripts\python.exe" -X utf8 main.py --port 8188 --listen 0.0.0.0 --extra-model-paths-config "E:\Ó°½³AI\ComfyUI\extra_model_paths.yaml" > "C:\Users\Seele\_comfyui_r.log" 2>&1
