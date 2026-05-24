const portSelect     = document.getElementById('port-select');
const connectBtn     = document.getElementById('connect-btn');
const scanBtn        = document.getElementById('scan-btn');
const recordBtn      = document.getElementById('record-btn');
const statusBadge    = document.getElementById('status-badge');
const recordingBadge = document.getElementById('recording-badge');
const logTerminal    = document.getElementById('log-terminal');

const tempVal        = document.getElementById('temp-val');
const humVal         = document.getElementById('hum-val');
const ldrVal         = document.getElementById('ldr-val');
const tempIndicator  = document.getElementById('temp-indicator');
const humIndicator   = document.getElementById('hum-indicator');
const ldrIndicator   = document.getElementById('ldr-indicator');

const plantLastTime  = document.getElementById('plant-last-time');
const plantReadings  = document.getElementById('plant-readings-count');

const _prev = { temp: null, hum: null, ldr: null };
let _totalReadings = 0;

// ─── Puerto ───────────────────────────────────────────────────────────────────

export function getPortValue() { return portSelect.value; }

export function populatePorts(ports, activePortName) {
    portSelect.innerHTML = '';
    if (ports.length === 0) {
        const opt = document.createElement('option');
        opt.value = ''; opt.textContent = 'Sin puertos';
        portSelect.appendChild(opt);
        return;
    }
    ports.forEach(port => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = port;
        portSelect.appendChild(opt);
    });
    if (activePortName)              portSelect.value = activePortName;
    else if (ports.includes('COM3')) portSelect.value = 'COM3';
    else                             portSelect.value = ports[0];
}

// ─── Estado de la UI ──────────────────────────────────────────────────────────

export function updateUIState({ isSocketConnected, isSerialConnected, isRecordingActive }) {
    if (!isSocketConnected) {
        statusBadge.textContent = 'Servidor Caído';
        statusBadge.className   = 'badge badge-disconnected';
        connectBtn.textContent  = 'Conectar';
        connectBtn.className    = 'btn btn-primary';
        connectBtn.disabled     = true;
        scanBtn.disabled        = true;
        recordBtn.disabled      = true;
        return;
    }

    connectBtn.disabled = false;
    scanBtn.disabled    = false;

    if (isSerialConnected) {
        statusBadge.textContent = `Conectado: ${portSelect.value}`;
        statusBadge.className   = 'badge badge-connected';
        connectBtn.textContent  = 'Desconectar';
        connectBtn.className    = 'btn btn-primary connected';
        portSelect.disabled     = true;
        recordBtn.disabled      = false;
    } else {
        statusBadge.textContent = 'Desconectado';
        statusBadge.className   = 'badge badge-disconnected';
        connectBtn.textContent  = 'Conectar';
        connectBtn.className    = 'btn btn-primary';
        portSelect.disabled     = false;
        recordBtn.disabled      = true;
    }

    updateRecordingUI({ isRecordingActive, isSerialConnected });
}

export function updateRecordingUI({ isRecordingActive, isSerialConnected }) {
    if (isRecordingActive && isSerialConnected) {
        recordingBadge.classList.remove('hidden');
        recordBtn.textContent = 'Detener Grabación';
        recordBtn.className   = 'btn btn-record recording-active';
    } else {
        recordingBadge.classList.add('hidden');
        recordBtn.textContent = 'Grabar Datos';
        recordBtn.className   = 'btn btn-record';
    }
}

// ─── Sensores ─────────────────────────────────────────────────────────────────

export function updateSensors(temp, hum, ldr) {
    tempVal.textContent = parseFloat(temp).toFixed(1);
    humVal.textContent  = parseFloat(hum).toFixed(1);
    ldrVal.textContent  = parseFloat(ldr).toFixed(1);
}

export function updateTrends(temp, hum, ldr) {
    _setTrend('temp', temp, tempIndicator);
    _setTrend('hum',  hum,  humIndicator);
    _setTrend('ldr',  ldr,  ldrIndicator);
}

export function updatePlantMeta() {
    _totalReadings++;
    plantReadings.textContent = _totalReadings;
    plantLastTime.textContent = new Date().toLocaleTimeString();
}

// ─── Terminal ─────────────────────────────────────────────────────────────────

export function logToTerminal(message, type = 'system') {
    const line = document.createElement('div');
    line.className   = `log-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logTerminal.appendChild(line);
    logTerminal.scrollTop = logTerminal.scrollHeight;
}

// ─── Privado ──────────────────────────────────────────────────────────────────

function _setTrend(key, value, element) {
    const prev = _prev[key];
    if (prev !== null) {
        const diff = value - prev;
        if (diff > 0.05) {
            element.textContent = 'Subiendo';
            element.className   = 'status-indicator text-rising';
        } else if (diff < -0.05) {
            element.textContent = 'Bajando';
            element.className   = 'status-indicator text-falling';
        } else {
            element.textContent = 'Estable';
            element.className   = 'status-indicator text-stable';
        }
    }
    _prev[key] = value;
}
