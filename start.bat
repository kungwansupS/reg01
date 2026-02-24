@echo off
setlocal EnableExtensions
chcp 65001 >nul
title REG-01 System Manager

:MENU
cls
echo ==================================================
echo              REG-01 SYSTEM MANAGER
echo ==================================================
echo.
echo [1] Start (check Docker and launch all services)
echo [2] Tunnel
echo [3] Install (check and install everything)
echo.
set /p choice=Select option (1-3): 

if "%choice%"=="1" goto START_ALL
if "%choice%"=="2" goto START_TUNNEL
if "%choice%"=="3" goto INSTALL_ALL
goto MENU

:START_ALL
echo Starting REG-01 services...
start "REG-01 Start" cmd /k ^
 "mode con cols=120 lines=40 && install\setup_auto.bat start"
goto MENU

:START_TUNNEL
echo Starting Tunnel...
start "REG-01 Tunnel" cmd /k ^
 "mode con cols=90 lines=20 && python tunnel.py"
goto MENU

:INSTALL_ALL
echo Starting full installer...
start "REG-01 Installer" cmd /k ^
 "mode con cols=120 lines=40 && install\setup_auto.bat"
goto MENU
