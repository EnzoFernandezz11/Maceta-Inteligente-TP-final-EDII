#!/bin/bash
cd "$(dirname "$0")"
echo "=============================================="
echo "Iniciando Servidor UART y WebSocket..."
echo "=============================================="
python3 -m backend.server &
SERVER_PID=$!
sleep 2
echo "=============================================="
echo "Abriendo Dashboard en el Navegador..."
echo "=============================================="
xdg-open http://localhost:8080/
echo "Servidor corriendo (PID $SERVER_PID). Presiona CTRL+C para detenerlo."
wait $SERVER_PID
