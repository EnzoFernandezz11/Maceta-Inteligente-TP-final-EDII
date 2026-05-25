import { logToTerminal, populatePorts, updateUIState, updateRecordingUI,
         updateSensors, updateTrends, updatePlantMeta } from './ui.js';
import { pushData }        from './charts.js';
import { updatePlantState } from './plant.js';

const SOCKET_URL = 'ws://localhost:8765';

let _socket         = null;
let _reconnectTimer = null;

let _isSocketConnected = false;
let _isSerialConnected = false;
let _isRecordingActive = false;

// ─── API pública ──────────────────────────────────────────────────────────────

export function connect() {
    logToTerminal('Intentando conectar con el servidor WebSocket...', 'system');
    _socket = new WebSocket(SOCKET_URL);

    _socket.onopen = () => {
        _isSocketConnected = true;
        logToTerminal('Conectado al servidor WebSocket.', 'success');
        clearTimeout(_reconnectTimer);
    };

    _socket.onclose = () => {
        _isSocketConnected = false;
        _isSerialConnected = false;
        _isRecordingActive = false;
        updateUIState(_state());
        updatePlantState(-1);
        logToTerminal('Conexión perdida. Reintentando en 3s...', 'error');
        clearTimeout(_reconnectTimer);
        _reconnectTimer = setTimeout(connect, 3000);
    };

    _socket.onerror = () => {};

    _socket.onmessage = ({ data }) => {
        try { _handleMessage(JSON.parse(data)); }
        catch (e) { logToTerminal(`Error parseando mensaje: ${e.message}`, 'error'); }
    };
}

export function sendCommand(payload) {
    if (_socket && _isSocketConnected) _socket.send(JSON.stringify(payload));
}

export function isSerialConnected() { return _isSerialConnected; }
export function isRecordingActive() { return _isRecordingActive; }

// ─── Manejo de mensajes ───────────────────────────────────────────────────────

function _handleMessage(data) {
    switch (data.type) {
        case 'init':
            logToTerminal(`Configuración recibida. Puertos: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, data.active_port);
            _isSerialConnected = data.status === 'connected';
            _isRecordingActive = data.recording ?? false;
            updateUIState(_state());
            if (_isSerialConnected) logToTerminal(`Reconectado a: ${data.active_port}`, 'success');
            break;

        case 'ports':
            logToTerminal(`Puertos: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, null);
            break;

        case 'status':
            _handleStatus(data);
            break;

        case 'recording_status':
            _isRecordingActive = data.recording;
            updateRecordingUI({ isRecordingActive: _isRecordingActive, isSerialConnected: _isSerialConnected });
            logToTerminal(
                _isRecordingActive ? 'Grabación iniciada.' : 'Grabación detenida.',
                _isRecordingActive ? 'success' : 'system',
            );
            break;

        case 'data':
            _handleData(data);
            break;
    }
}

function _handleStatus(data) {
    if (data.status === 'connected') {
        _isSerialConnected = true;
        logToTerminal(`Puerto serial conectado: ${data.port}`, 'success');
    } else if (data.status === 'disconnected') {
        _isSerialConnected = false;
        _isRecordingActive = false;
        logToTerminal('Puerto serial desconectado.', 'system');
        updatePlantState(-1);
    } else if (data.status === 'error') {
        logToTerminal(`Error serial: ${data.message}`, 'error');
    }
    updateUIState(_state());
}

function _handleData(data) {
    updateSensors(data.temp, data.hum, data.ldr);
    updateTrends(data.temp, data.hum, data.ldr);
    pushData('temp', data.temp);
    pushData('hum',  data.hum);
    pushData('ldr',  data.ldr);
    updatePlantState(data.alert ?? -1);
    updatePlantMeta();
}

function _state() {
    return {
        isSocketConnected: _isSocketConnected,
        isSerialConnected: _isSerialConnected,
        isRecordingActive: _isRecordingActive,
    };
}
