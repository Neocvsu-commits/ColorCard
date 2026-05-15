@echo off
:: 修复管理员运行时的路径偏移问题
cd /d "%~dp0"
:: 切换为 UTF-8 编码防乱码，并将提示输出重定向
chcp 65001 >nul

title TA 管线自动打包工具 (交付版)

echo =========================================
echo       TA 管线自动打包与发行收纳工具
echo =========================================
echo.

:: [终极防呆 1]：支持直接将 .py 文件拖拽到本 .bat 脚本图标上运行
set "TOOL_NAME=%~n1"

:: 如果没有直接拖拽文件，则进入交互模式
if "%TOOL_NAME%"=="" (
    echo 请输入要打包的 Python 文件名 
    echo (提示：你可以直接把 .py 文件拖进这个黑框里，然后按回车)
    set /p INPUT_NAME="> "
)

:: [终极防呆 2]：处理用户的各种手滑输入
if "%TOOL_NAME%"=="" (
    if "%INPUT_NAME%"=="" (
        echo.
        echo [错误] 文件名不能为空！
        echo.
        pause
        exit
    )
    :: 去除用户拖拽文件时系统自带的双引号和后缀
    set "INPUT_NAME=%INPUT_NAME:"=%"
    set "INPUT_NAME=%INPUT_NAME:.py=%"
    for %%i in ("%INPUT_NAME%") do set "TOOL_NAME=%%~ni"
)

:: 二次确认文件是否存在
if not exist "%TOOL_NAME%.py" (
    echo.
    echo [错误] 找不到源码文件 "%TOOL_NAME%.py" ！
    echo.
    pause
    exit
)

:: 设定管线收纳目录
set ROOT_FOLDER=Python_Tool
set OUT_FOLDER=%ROOT_FOLDER%\%TOOL_NAME%
set VENV_FOLDER=%ROOT_FOLDER%\venv_build

echo.
echo =========================================
echo    开始打包: %TOOL_NAME%.py
echo    交付目录: %OUT_FOLDER%
echo =========================================
echo.

:: [1] 创建管线目录结构
if not exist "%ROOT_FOLDER%" mkdir "%ROOT_FOLDER%"
if not exist "%OUT_FOLDER%" mkdir "%OUT_FOLDER%"

:: [2] 检查并创建纯净虚拟环境
if not exist "%VENV_FOLDER%" (
    echo [1/5] 正在创建纯净虚拟环境...
    python -m venv "%VENV_FOLDER%"
) else (
    echo [1/5] 发现纯净虚拟环境，直接复用...
)

:: [3] 激活环境并检查核心依赖
echo [2/5] 激活环境并检查核心依赖...
call "%VENV_FOLDER%\Scripts\activate"
python -m pip install --upgrade pip -q
pip install pyinstaller pillow -q

:: [4] 彻底清理历史缓存
echo [3/5] 正在清理历史版本与缓存...
rmdir /s /q "%OUT_FOLDER%\bin" 2>nul
rmdir /s /q "%OUT_FOLDER%\build" 2>nul
rmdir /s /q "%OUT_FOLDER%\temp" 2>nul
del /q "%OUT_FOLDER%\*.spec" 2>nul
del /q "%OUT_FOLDER%\*.lnk" 2>nul

:: [5] 采用目录模式(-D)编译，极大提升软件启动速度
echo [4/5] 正在编译底层框架，这可能需要几十秒...
pyinstaller -D -w --clean ^
    --distpath "%OUT_FOLDER%\temp" ^
    --workpath "%OUT_FOLDER%\build" ^
    --specpath "%OUT_FOLDER%" ^
    -n "%TOOL_NAME%_Pro" "%TOOL_NAME%.py"

:: [6] 整理交付文件夹，将乱七八糟的底层文件隐藏进 bin 目录
echo [5/5] 正在生成交付文件夹与快捷方式...
move "%OUT_FOLDER%\temp\%TOOL_NAME%_Pro" "%OUT_FOLDER%\bin" >nul
rmdir /s /q "%OUT_FOLDER%\temp" 2>nul
rmdir /s /q "%OUT_FOLDER%\build" 2>nul
del /q "%OUT_FOLDER%\*.spec" 2>nul

:: [7] 动态生成 VBS 脚本，自动创建指向 bin 内部的快捷方式
set VBS_SCRIPT="%TEMP%\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_SCRIPT%
echo sLinkFile = "%~dp0%OUT_FOLDER%\运行_%TOOL_NAME%.lnk" >> %VBS_SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_SCRIPT%
echo oLink.TargetPath = "%~dp0%OUT_FOLDER%\bin\%TOOL_NAME%_Pro.exe" >> %VBS_SCRIPT%
echo oLink.WorkingDirectory = "%~dp0%OUT_FOLDER%\bin" >> %VBS_SCRIPT%
echo oLink.Description = "%TOOL_NAME% 专业工具" >> %VBS_SCRIPT%
echo oLink.Save >> %VBS_SCRIPT%

cscript /nologo %VBS_SCRIPT%
del %VBS_SCRIPT%

:: 退出虚拟环境
deactivate

echo.
echo =========================================
echo  交付包生成完毕！
echo  结构如下：
echo  📂 %TOOL_NAME%
echo   ├── 📁 bin (核心依赖库)
echo   └── 🔗 运行_%TOOL_NAME% (快捷方式)
echo.
echo  请直接将 [%OUT_FOLDER%] 文件夹打成压缩包发给客户！
echo =========================================
pause