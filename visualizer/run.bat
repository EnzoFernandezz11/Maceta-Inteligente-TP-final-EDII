@echo off
title UART Sensor Dashboard
cd /d "%~dp0"

echo ====================================================
echo   SENSORY UART DASHBOARD - INICIANDO SISTEMA
echo ====================================================
echo.

:: Ejecutar el servidor Python. Python se encargará de abrir el navegador de forma robusta.
python server.py

echo.
echo ----------------------------------------------------
echo   El servidor se ha detenido o ha ocurrido un error.
echo ----------------------------------------------------
pause
