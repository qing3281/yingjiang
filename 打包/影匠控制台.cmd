@echo off
chcp 65001 >nul
title 影匠控制台

rem ★ 这一版起的是「打包好的 exe」，不再需要 python 环境。
rem   exe 自己认它所在的目录当根 —— 所以它必须待在 D:\DSHworkspace\影匠\，
rem   跟「作品\」在同一个目录里。

powershell -NoProfile -Command "try{(Invoke-WebRequest 'http://127.0.0.1:8791/' -UseBasicParsing -TimeoutSec 3)|Out-Null; exit 0}catch{exit 1}"
if errorlevel 1 goto 起
start "" "http://127.0.0.1:8791/"
exit /b 0

:起
echo   正在起「影匠控制台」，浏览器马上会自己打开…
start "" "D:\DSHworkspace\影匠\影匠控制台.exe"
exit /b 0
