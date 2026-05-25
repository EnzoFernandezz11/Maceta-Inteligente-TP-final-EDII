@echo off
title UART Sensor Dashboard
cd /d "%~dp0"
echo ==============================================
echo Iniciando Servidor UART y WebSocket...
echo ==============================================
start "" python -m backend.server
timeout /t 2 /nobreak >nul
echo ==============================================
echo Abriendo Dashboard en el Navegador...
echo ==============================================
start "" http://localhost:8080/
echo Servidor corriendo. Puedes cerrar esta ventana presionando CTRL+C o cerrando la consola.
