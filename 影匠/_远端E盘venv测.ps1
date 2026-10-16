$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. pyvenv.cfg 内容（看 venv 指哪）==="
Get-Content -LiteralPath "$新程序\.venv\pyvenv.cfg" -Raw -EA SilentlyContinue

"=== 2. E 盘的 venv 能起来吗 ==="
& $py -c "import sys; print('  python', sys.version.split()[0]); print('  exe  ', sys.executable); print('  prefix', sys.prefix)" 2>&1

"=== 3. 关键依赖还在吗 ==="
& $py -c "import torch, torchvision, numpy, PIL, aiohttp, yaml; print('  torch', torch.__version__, '| cuda', torch.version.cuda, '| avail', torch.cuda.is_available()); print('  numpy', numpy.__version__, '| pillow', PIL.__version__)" 2>&1 | Select-Object -First 6

"=== 4. CUDA 能认到卡吗 ==="
& $py -c "import torch; print('  卡:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA 不可用')" 2>&1

"=== 5. ComfyUI 自己能不能从 E 盘 import ==="
Push-Location $新程序
& $py -c "import folder_paths; print('  folder_paths OK'); print('  models 根:', folder_paths.models_dir); import nodes; print('  nodes OK')" 2>&1 | Select-Object -First 8
Pop-Location

"=== 6. extra_model_paths 里写的路径能被解析吗 ==="
& $py -c @"
import sys
sys.path.insert(0, r'$新程序')
import folder_paths, yaml, os
p = r'$新程序\extra_model_paths.yaml'
cfg = yaml.safe_load(open(p, encoding='utf-8'))
base = cfg['comfyui']['base_path']
print('  base_path:', base, '存在:', os.path.isdir(base))
for k, v in cfg['comfyui'].items():
    if k == 'base_path': continue
    d = os.path.join(base, v)
    n = len(os.listdir(d)) if os.path.isdir(d) else -1
    print('   {0:18s} {1:6d} 项  {2}'.format(k, n, d))
"@ 2>&1
