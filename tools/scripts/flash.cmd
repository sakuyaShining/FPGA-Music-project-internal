@echo off
REM ===========================================================================
REM  flash.cmd  --  把码流烧进 FPGA（SRAM 模式，掉电丢失，开发期用这个）
REM
REM  用法：
REM     tools\scripts\flash.cmd                          <- 烧默认工程
REM     tools\scripts\flash.cmd led_blink                <- 烧指定工程名
REM     tools\scripts\flash.cmd led_blink.gprj           <- 也可以带扩展名
REM
REM  原理：在 src\gowin\ 下找同名工程，取它的 impl\pnr\<名>.fs 烧进去
REM
REM  为什么用 SRAM 而不是 Flash：
REM     SRAM 烧录 ~4 秒、可无限次重写、零风险、掉电即消失。
REM     开发阶段就应该用 SRAM；只有设计冻结后才考虑固化到 Flash。
REM ===========================================================================
setlocal enabledelayedexpansion

REM --- 工具路径 ---------------------------------------------------------------
set "GOWIN_HOME=D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64"
set "PC=%GOWIN_HOME%\Programmer\bin\programmer_cli.exe"

REM --- 项目根目录（%~dp0 = tools\scripts\ ，往上两级）-------------------------
set "ROOT=%~dp0..\.."
set "GOWIN_DIR=%ROOT%\src\gowin"

REM --- 确定要烧哪个工程 -------------------------------------------------------
set "PROJ=%~1"
if "%PROJ%"=="" set "PROJ=led_blink"
REM 去掉可能带的 .gprj 后缀
set "PROJ=%PROJ:.gprj=%"

set "FS=%GOWIN_DIR%\%PROJ%\impl\pnr\%PROJ%.fs"

echo.
echo ============================================================
echo   烧录 SRAM
echo ============================================================
echo   工程   : %PROJ%
echo   码流   : %FS%
echo.

REM --- 检查工具 ---------------------------------------------------------------
if not exist "%PC%" (
    echo [X] 找不到 programmer_cli.exe
    echo     期望位置: %PC%
    echo     请确认 Gowin EDA 是否装在 D:\FPGA-Project\Gowin\
    echo.
    pause
    exit /b 1
)

REM --- 检查码流 ---------------------------------------------------------------
if not exist "%FS%" (
    echo [X] 找不到码流文件
    echo     期望位置: %FS%
    echo.
    echo     可能是还没编译。先跑：
    echo         tools\scripts\build_gowin.ps1 -Project src\gowin\%PROJ%.gprj
    echo.
    echo     现有可用码流：
    for /d %%D in ("%GOWIN_DIR%\*") do (
        if exist "%%D\impl\pnr\%%~nxD.fs" echo         %%~nxD
    )
    echo.
    pause
    exit /b 1
)

REM --- 列出可用的下载器 -------------------------------------------------------
echo --- 检测下载器 ---
"%PC%" --scan
echo.

REM --- 烧录 -------------------------------------------------------------------
echo --- 开始烧录 ---
"%PC%" --device GW2AR-18C --operation_index 1 --fsFile "%FS%"

if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   [OK] 烧录命令已发出
echo ============================================================
echo   板子上应该立刻出现现象（比如 LED 开始跑马灯）。
echo   注意：SRAM 掉电即失，拔电重插就没了 —— 这是正常的。
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   [X] 烧录失败 —— 排查清单
echo ============================================================
echo   1. 板子插的是不是【带数据】的 USB 线？（有些线只能供电）
echo   2. 换一个 USB 口试试（别用前面板 / 无供电的 HUB）
echo   3. 等 10 秒让驱动加载完再跑一次
echo   4. 打开设备管理器，应该能看到：
echo        - USB Serial Converter A
echo        - USB Serial Converter B
echo        - Gowin USB Cable
echo      少了任何一个 = 驱动没装好（重装 Programmer\driver 下的驱动）
echo   5. 确认板子的电源灯亮着
echo.
pause
exit /b 1
