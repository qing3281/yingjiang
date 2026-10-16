import sys, os, types
root = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
os.chdir(root)
sys.path.insert(0, root)
sys.path.insert(0, root + r"\custom_nodes")

# --- 桩：模拟 ComfyUI 已启动时的 server.PromptServer ---
import server as _server
class _Routes:
    def get(self, *a, **k):
        def deco(f): return f
        return deco
    def post(self, *a, **k):
        def deco(f): return f
        return deco
class _PS:
    instance = None
    def __init__(self):
        self.routes = _Routes()
_PS.instance = _PS()
_server.PromptServer = _PS

import importlib
m = importlib.import_module("ComfyUI-Index-TTS")
ks = sorted(m.NODE_CLASS_MAPPINGS.keys())
print("IMPORT_OK")
print("NODE_COUNT", len(ks))
for k in ks:
    print("  ", k)