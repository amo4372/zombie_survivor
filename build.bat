@echo off
REM 丧尸幸存者 - Windows 打包脚本

echo === 丧尸幸存者打包脚本 ===

REM 检查 Python
python --version || (echo 需要安装 Python & exit /b 1)

REM 安装依赖
echo 安装依赖...
pip install -r requirements.txt

REM 创建 spec 文件
echo 创建 PyInstaller spec...
pyi-makespec --onefile --windowed ^
    --add-data "assets/images;assets/images" ^
    --add-data "assets/sounds;assets/sounds" ^
    --add-data "assets/music;assets/music" ^
    --name "ZombieSurvivor" ^
    main.py

REM 打包
echo 开始打包...
pyinstaller ZombieSurvivor.spec

echo === 打包完成 ===
echo 输出目录: dist\ZombieSurvivor.exe
echo.
echo 注意: 请将资源文件放入 assets\ 目录后再运行
pause
