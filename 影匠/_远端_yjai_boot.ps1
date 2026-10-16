# C:\yjai_boot.ps1 —— 开机拉起远端 ComfyUI
# 关键：本文件存成 UTF-8 BOM，PowerShell 5.1 能正确读中文；
#       再用 WMI 起进程（WMI 命令行是 Unicode，不经过 cmd 的 OEM 代码页）。
$sysPy = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'
Start-Sleep -Seconds 20
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = '"{0}" C:\yjai_run.py 8188' -f $sysPy
} | Out-Null