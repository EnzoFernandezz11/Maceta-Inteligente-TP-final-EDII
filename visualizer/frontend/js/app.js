import { connect, sendCommand, isSerialConnected, isRecordingActive } from './ws_client.js';
import { initCharts } from './charts.js';
import { logToTerminal, getPortValue } from './ui.js';

function setupEventListeners() {
    document.getElementById('connect-btn').addEventListener('click', () => {
        if (isSerialConnected()) {
            logToTerminal('Solicitando desconexión...', 'system');
            sendCommand({ command: 'disconnect' });
        } else {
            const port = getPortValue();
            if (!port) { logToTerminal('Seleccione un puerto COM válido.', 'error'); return; }
            logToTerminal(`Conectando a ${port}...`, 'system');
            sendCommand({ command: 'connect', port });
        }
    });

    document.getElementById('scan-btn').addEventListener('click', () => {
        logToTerminal('Buscando puertos COM...', 'system');
        sendCommand({ command: 'get_ports' });
    });

    document.getElementById('record-btn').addEventListener('click', () => {
        sendCommand({ command: isRecordingActive() ? 'stop_recording' : 'start_recording' });
    });

    document.getElementById('clear-log-btn').addEventListener('click', () => {
        document.getElementById('log-terminal').innerHTML = '';
        logToTerminal('Consola limpia.', 'system');
    });
}

function init() {
    setupEventListeners();
    initCharts();
    connect();
}

window.addEventListener('DOMContentLoaded', init);
