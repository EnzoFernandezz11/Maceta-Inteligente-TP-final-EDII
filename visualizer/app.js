// ─── DOM References ──────────────────────────────────────────────────────────
const portSelect       = document.getElementById('port-select');
const scanBtn          = document.getElementById('scan-btn');
const connectBtn       = document.getElementById('connect-btn');
const recordBtn        = document.getElementById('record-btn');
const statusBadge      = document.getElementById('status-badge');
const recordingBadge   = document.getElementById('recording-badge');
const logTerminal      = document.getElementById('log-terminal');
const clearLogBtn      = document.getElementById('clear-log-btn');

const tempVal          = document.getElementById('temp-val');
const tempIndicator    = document.getElementById('temp-indicator');
const humVal           = document.getElementById('hum-val');
const humIndicator     = document.getElementById('hum-indicator');
const ldrVal           = document.getElementById('ldr-val');
const ldrIndicator     = document.getElementById('ldr-indicator');

const plantSvg         = document.getElementById('plant-svg');
const plantStateBadge  = document.getElementById('plant-state-badge');
const plantClassText   = document.getElementById('plant-class-text');
const plantLastTime    = document.getElementById('plant-last-time');
const plantReadings    = document.getElementById('plant-readings-count');
const plantAlertMsg    = document.getElementById('plant-alert-msg');
const plantAlertText   = document.getElementById('plant-alert-text');

// ─── WebSocket State ──────────────────────────────────────────────────────────
let socket           = null;
const socketUrl      = 'ws://localhost:8765';
let isSocketConnected  = false;
let isSerialConnected  = false;
let isRecordingActive  = false;
let reconnectTimer     = null;
let totalReadings      = 0;

// ─── Chart History ────────────────────────────────────────────────────────────
const MAX_CHART_POINTS = 40;
const history    = { temp: [], hum: [], ldr: [] };
const prevValues = { temp: null, hum: null, ldr: null };

// ─── ECharts Instances ────────────────────────────────────────────────────────
let chartTemp = null;
let chartHum  = null;
let chartLdr  = null;

// ─── Plant State Map ──────────────────────────────────────────────────────────
const PLANT_STATES = {
    '-1': { cls: 'plant-idle', badge: 'badge-state-idle', label: 'Sin datos',      alert: false },
     '0': { cls: 'plant-ok',   badge: 'badge-state-ok',   label: 'Saludable',      alert: false },
     '1': { cls: 'plant-dry',  badge: 'badge-state-dry',  label: 'Necesita Riego', alert: true,
             msg: 'Humedad baja detectada. La planta necesita agua.' },
     '2': { cls: 'plant-sun',  badge: 'badge-state-sun',  label: 'Demasiado Sol',  alert: true,
             msg: 'Temperatura y/o luz excesiva. Mover la planta a la sombra.' },
};

const CLASS_LABELS = {
    '-1': 'Perceptrón esperando...',
     '0': 'Clase 0 — Condiciones normales',
     '1': 'Clase 1 — Riego necesario',
     '2': 'Clase 2 — Exposición solar excesiva',
};

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
    setupEventListeners();
    initCharts();
    connectWebSocket();
}

// ─── ECharts ──────────────────────────────────────────────────────────────────
function initCharts() {
    chartTemp = echarts.init(document.getElementById('chart-temp'), null, { renderer: 'canvas' });
    chartHum  = echarts.init(document.getElementById('chart-hum'),  null, { renderer: 'canvas' });
    chartLdr  = echarts.init(document.getElementById('chart-ldr'),  null, { renderer: 'canvas' });

    chartTemp.setOption(makeChartOption('#d9383a', 15, 35));
    chartHum.setOption(makeChartOption('#107c41',   0, 100));
    chartLdr.setOption(makeChartOption('#b7791f',   0, 100));

    window.addEventListener('resize', () => {
        chartTemp.resize();
        chartHum.resize();
        chartLdr.resize();
    });
}

function makeChartOption(hexColor, minVal, maxVal) {
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    return {
        animation: false,
        grid: { top: 3, bottom: 3, left: 0, right: 0 },
        xAxis: { type: 'category', show: false, boundaryGap: false, data: [] },
        yAxis: { type: 'value', show: false, min: minVal, max: maxVal },
        tooltip: {
            trigger: 'axis',
            formatter: params => params[0].value.toFixed(1),
            backgroundColor: 'rgba(17,17,17,0.82)',
            borderColor: 'transparent',
            padding: [4, 8],
            textStyle: { color: '#fff', fontSize: 11, fontFamily: 'monospace' },
        },
        series: [{
            type: 'line',
            smooth: true,
            symbol: 'none',
            data: [],
            lineStyle: { width: 2.2, color: hexColor },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${r},${g},${b},0.14)` },
                    { offset: 1, color: `rgba(${r},${g},${b},0.01)` },
                ]),
            },
        }],
    };
}

function updateChart(chart, dataArr) {
    if (!chart || dataArr.length < 2) return;
    chart.setOption({
        xAxis: { data: dataArr.map((_, i) => i) },
        series: [{ data: dataArr }],
    });
}

// ─── Plant State ──────────────────────────────────────────────────────────────
function updatePlantState(alert) {
    const key   = String(alert !== undefined && alert !== null ? alert : -1);
    const state = PLANT_STATES[key] || PLANT_STATES['-1'];

    plantSvg.setAttribute('class', state.cls);
    plantStateBadge.className   = `plant-state-badge ${state.badge}`;
    plantStateBadge.textContent = state.label;
    plantClassText.textContent  = CLASS_LABELS[key] || 'Clasificación desconocida';

    if (state.alert) {
        plantAlertMsg.classList.remove('hidden');
        plantAlertText.textContent = state.msg;
    } else {
        plantAlertMsg.classList.add('hidden');
    }
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWebSocket() {
    logToTerminal('Intentando conectar con el servidor WebSocket...', 'system');
    socket = new WebSocket(socketUrl);

    socket.onopen = () => {
        isSocketConnected = true;
        logToTerminal('Conectado al servidor WebSocket.', 'success');
        clearTimeout(reconnectTimer);
    };

    socket.onclose = () => {
        isSocketConnected  = false;
        isSerialConnected  = false;
        isRecordingActive  = false;
        updateUIState();
        updatePlantState(-1);
        logToTerminal('Conexión con el servidor perdida. Reintentando en 3s...', 'error');
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = () => {};

    socket.onmessage = (event) => {
        try {
            handleServerMessage(JSON.parse(event.data));
        } catch (e) {
            logToTerminal(`Error parseando mensaje: ${e.message}`, 'error');
        }
    };
}

function handleServerMessage(data) {
    switch (data.type) {
        case 'init':
            logToTerminal(`Configuración recibida. Puertos: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, data.active_port);
            isSerialConnected = (data.status === 'connected');
            isRecordingActive = data.recording || false;
            updateUIState();
            if (isSerialConnected) logToTerminal(`Reconectado a sesión activa en: ${data.active_port}`, 'success');
            break;

        case 'ports':
            logToTerminal(`Puertos actualizados: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, null);
            break;

        case 'status':
            handleStatusMessage(data);
            break;

        case 'recording_status':
            isRecordingActive = data.recording;
            updateRecordingUI();
            logToTerminal(isRecordingActive ? 'Grabación iniciada en sensor_data.csv' : 'Grabación detenida.', isRecordingActive ? 'success' : 'system');
            break;

        case 'data':
            handleIncomingData(data);
            break;
    }
}

function handleStatusMessage(data) {
    if (data.status === 'connected') {
        isSerialConnected = true;
        logToTerminal(`Puerto serial conectado: ${data.port}`, 'success');
    } else if (data.status === 'disconnected') {
        isSerialConnected = false;
        isRecordingActive = false;
        logToTerminal('Puerto serial desconectado.', 'system');
        updatePlantState(-1);
    } else if (data.status === 'error') {
        logToTerminal(`Error serial: ${data.message}`, 'error');
    }
    updateUIState();
}

// ─── Incoming Data ────────────────────────────────────────────────────────────
function handleIncomingData(data) {
    const temp = parseFloat(data.temp).toFixed(1);
    const hum  = parseFloat(data.hum).toFixed(1);
    const ldr  = parseFloat(data.ldr).toFixed(1);

    tempVal.textContent = temp;
    humVal.textContent  = hum;
    ldrVal.textContent  = ldr;

    updateTrend('temp', data.temp, tempIndicator);
    updateTrend('hum',  data.hum,  humIndicator);
    updateTrend('ldr',  data.ldr,  ldrIndicator);

    appendChartData('temp', data.temp);
    appendChartData('hum',  data.hum);
    appendChartData('ldr',  data.ldr);

    updateChart(chartTemp, history.temp);
    updateChart(chartHum,  history.hum);
    updateChart(chartLdr,  history.ldr);

    updatePlantState(data.alert !== undefined ? data.alert : -1);

    totalReadings++;
    plantReadings.textContent = totalReadings;
    plantLastTime.textContent = new Date().toLocaleTimeString();
}

function updateTrend(key, currentVal, element) {
    const prev = prevValues[key];
    if (prev !== null) {
        const diff = currentVal - prev;
        if (diff > 0.05) {
            element.textContent = 'Subiendo';
            element.className = 'status-indicator text-rising';
        } else if (diff < -0.05) {
            element.textContent = 'Bajando';
            element.className = 'status-indicator text-falling';
        } else {
            element.textContent = 'Estable';
            element.className = 'status-indicator text-stable';
        }
    }
    prevValues[key] = currentVal;
}

function appendChartData(key, value) {
    history[key].push(value);
    if (history[key].length > MAX_CHART_POINTS) history[key].shift();
}

// ─── UI State ─────────────────────────────────────────────────────────────────
function populatePorts(ports, activePortName) {
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

    if (activePortName)          portSelect.value = activePortName;
    else if (ports.includes('COM3')) portSelect.value = 'COM3';
    else                         portSelect.value = ports[0];
}

function updateUIState() {
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

    updateRecordingUI();
}

function updateRecordingUI() {
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

function logToTerminal(message, type = 'system') {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className   = `log-line ${type}`;
    line.textContent = `[${time}] ${message}`;
    logTerminal.appendChild(line);
    logTerminal.scrollTop = logTerminal.scrollHeight;
}

// ─── Event Listeners ──────────────────────────────────────────────────────────
function setupEventListeners() {
    connectBtn.addEventListener('click', () => {
        if (!isSocketConnected) return;
        if (isSerialConnected) {
            logToTerminal(`Desconectando de ${portSelect.value}...`, 'system');
            socket.send(JSON.stringify({ command: 'disconnect' }));
        } else {
            const port = portSelect.value;
            if (!port) { logToTerminal('Seleccione un puerto COM válido.', 'error'); return; }
            logToTerminal(`Conectando a ${port}...`, 'system');
            socket.send(JSON.stringify({ command: 'connect', port }));
        }
    });

    scanBtn.addEventListener('click', () => {
        if (!isSocketConnected) return;
        logToTerminal('Buscando puertos COM disponibles...', 'system');
        socket.send(JSON.stringify({ command: 'get_ports' }));
    });

    recordBtn.addEventListener('click', () => {
        if (!isSocketConnected || !isSerialConnected) return;
        socket.send(JSON.stringify({ command: isRecordingActive ? 'stop_recording' : 'start_recording' }));
    });

    clearLogBtn.addEventListener('click', () => {
        logTerminal.innerHTML = '';
        logToTerminal('Consola limpia.', 'system');
    });
}

window.addEventListener('DOMContentLoaded', init);
