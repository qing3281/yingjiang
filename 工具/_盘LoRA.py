import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
def 问(路):
    with urllib.request.urlopen("http://127.0.0.1:8188" + 路, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))
print("── 本机 24 个 LoRA 全名单 ──")
for i, x in enumerate(问("/models/loras"), 1):
    print("   %2d. %s" % (i, x))
print("\n── 15 个 diffusion_models 全名单 ──")
for i, x in enumerate(问("/models/diffusion_models"), 1):
    print("   %2d. %s" % (i, x))
