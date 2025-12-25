@echo off
chcp 65001 >nul
title REG-01 System Manager

:MENU
cls
echo ==================================================
echo        REG-01 SYSTEM MANAGER
echo ==================================================
echo.
echo [1] Start Backend (run.py)
echo [2] Start Tunnel  (tunnel.py)
echo [3] Start Backend + Tunnel
echo [4] Run Install Requirements (install_requirements.py)
echo [5] Stop All (close python processes)
echo [0] Exit
echo.
set /p choice=Select option: 

if "%choice%"=="1" goto START_BACKEND
if "%choice%"=="2" goto START_TUNNEL
if "%choice%"=="3" goto START_BOTH
if "%choice%"=="4" goto INSTALL_REQ
if "%choice%"=="5" goto STOP_ALL
if "%choice%"=="0" exit

goto MENU

:: ===============================
:: Start Backend
:: ===============================
:START_BACKEND
echo Starting Backend...
start "REG-01 Backend" cmd /k ^
 "mode con cols=120 lines=40 && python run.py"
goto MENU

:: ===============================
:: Start Tunnel (Small Window)
:: ===============================
:START_TUNNEL
echo Starting Tunnel...
start "REG-01 Tunnel" cmd /k ^
 "mode con cols=90 lines=15 && python tunnel.py"
goto MENU

:: ===============================
:: Start Both
:: ===============================
:START_BOTH
echo Starting Backend and Tunnel...
start "REG-01 Backend" cmd /k ^
 "mode con cols=120 lines=40 && python run.py"

timeout /t 2 >nul

start "REG-01 Tunnel" cmd /k ^
 "mode con cols=90 lines=15 && python tunnel.py"
goto MENU

:: ===============================
:: Install Requirements
:: ===============================
:INSTALL_REQ
echo Running install_requirements.py ...
start "REG-01 Installer" cmd /k ^
 "mode con cols=110 lines=30 && python install_requirements.py"
goto MENU

:: ===============================
:: Stop All
:: ===============================
:STOP_ALL
echo Stopping all python processes...
taskkill /F /IM python.exe >nul 2>&1
echo Done.
timeout /t 2 >nul
goto MENU
