@echo off
REM 丧尸幸存者 - Windows 打包脚本（不内嵌资源，仅打包二进制）
echo === 丧尸幸存者打包脚本 ===
REM 检查 Python
python --version || (echo 需要安装 Python & exit /b 1)
REM 安装依赖
echo 安装依赖...
pip install -r requirements.txt
REM 安装 PyInstaller
pip install pyinstaller
REM 清理旧的构建文件
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ZombieSurvivor.spec del /q ZombieSurvivor.spec
REM 打包（仅二进制，资源文件放在exe同级的assets目录）
echo 开始打包...
pyinstaller --onefile --windowed --name "ZombieSurvivor" main.py
echo === 打包完成 ===
echo 输出目录: dist\ZombieSurvivor.exe
echo.
echo 重要: 请将 assets\ 目录复制到 dist\ 下，与 exe 同级
echo 目录结构:
echo   dist\
echo     ZombieSurvivor.exe
echo     assets\
echo       images\
echo       sounds\
echo       music\
pause
