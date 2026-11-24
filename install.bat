@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   TikTok Scraper MCP - 1-Click Automated Setup (CMD)
echo ============================================================

REM Check Python command
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PY_CMD=python
    goto RUN_INSTALL
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set PY_CMD=py
    goto RUN_INSTALL
)

echo [ERROR] Python 3.10+ tidak ditemukan di PATH.
echo Silakan download dan instal Python dari: https://www.python.org/downloads/
echo Pastikan opsi "Add python.exe to PATH" dicentang saat instalasi.
echo.
pause
exit /b 1

:RUN_INSTALL
%PY_CMD% install.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Proses instalasi gagal.
    pause
    exit /b %errorlevel%
)

echo.
echo [SELESAI] Instalasi berhasil. Silakan restart Claude Desktop.
exit /b 0
