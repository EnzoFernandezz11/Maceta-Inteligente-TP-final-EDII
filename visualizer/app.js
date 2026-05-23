// DOM Elements
const portSelect = document.getElementById('port-select');
const scanBtn = document.getElementById('scan-btn');
const connectBtn = document.getElementById('connect-btn');
const recordBtn = document.getElementById('record-btn');
const statusBadge = document.getElementById('status-badge');
const recordingBadge = document.getElementById('recording-badge');
const logTerminal = document.getElementById('log-terminal');
const clearLogBtn = document.getElementById('clear-log-btn');

// Sensor Values DOM
const tempVal = document.getElementById('temp-val');
const tempIndicator = document.getElementById('temp-indicator');
const humVal = document.getElementById('hum-val');
const humIndicator = document.getElementById('hum-indicator');
const ldrVal = document.getElementById('ldr-val');
const ldrIndicator = document.getElementById('ldr-indicator');

// WebSocket state
let socket = null;
const socketUrl = 'ws://localhost:8765';
let isSocketConnected = false;
let isSerialConnected = false;
let isRecordingActive = false;
let reconnectTimer = null;

// History for SVG Charts (Max 40 points)
const MAX_CHART_POINTS = 40;
const history = {
    temp: [],
    hum: [],
    ldr: []
};

// Map of previous values to check trends (rising, falling, stable)
const prevValues = {
    temp: null,
    hum: null,
    ldr: null
};

// Initialize app
function init() {
    setupEventListeners();
    connectWebSocket();
}

// Log messages to the terminal
function logToTerminal(message, type = 'system') {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = `[${time}] ${message}`;
    logTerminal.appendChild(line);
    
    // Auto-scroll to bottom
    logTerminal.scrollTop = logTerminal.scrollHeight;
}

// Connect to WebSocket Server
function connectWebSocket() {
    logToTerminal('Intentando conectar con el servidor WebSocket...', 'system');
    socket = new WebSocket(socketUrl);

    socket.onopen = () => {
        isSocketConnected = true;
        logToTerminal('Conectado al servidor WebSocket.', 'success');
        clearTimeout(reconnectTimer);
    };

    socket.onclose = () => {
        isSocketConnected = false;
        isSerialConnected = false;
        isRecordingActive = false;
        updateUIState();
        logToTerminal('Conexión con el servidor perdida. Reintentando en 3s...', 'error');
        
        // Try to reconnect
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (error) => {
        // Socket errors are logged silently, handled by onclose
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        } catch (e) {
            logToTerminal(`Error parseando mensaje: ${e.message}`, 'error');
        }
    };
}

// Handle messages from Python WebSocket server
function handleServerMessage(data) {
    switch (data.type) {
        case 'init':
            logToTerminal(`Configuración recibida. Puertos: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, data.active_port);
            isSerialConnected = (data.status === 'connected');
            isRecordingActive = data.recording || false;
            updateUIState();
            if (isSerialConnected) {
                logToTerminal(`Reconectado a sesión activa en puerto: ${data.active_port}`, 'success');
            }
            break;
            
        case 'ports':
            logToTerminal(`Lista de puertos actualizada: [${data.ports.join(', ')}]`, 'system');
            populatePorts(data.ports, null);
            break;
            
        case 'status':
            handleStatusMessage(data);
            break;
            
        case 'recording_status':
            isRecordingActive = data.recording;
            updateRecordingUI();
            if (isRecordingActive) {
                logToTerminal('Grabación iniciada en sensor_data.csv', 'success');
            } else {
                logToTerminal('Grabación detenida. Datos guardados.', 'system');
            }
            break;
            
        case 'data':
            handleIncomingData(data);
            break;
    }
}

// Handle connection/status messages from server
function handleStatusMessage(data) {
    if (data.status === 'connected') {
        isSerialConnected = true;
        logToTerminal(`Puerto serial conectado con éxito: ${data.port}`, 'success');
    } else if (data.status === 'disconnected') {
        isSerialConnected = false;
        isRecordingActive = false;
        logToTerminal('Puerto serial desconectado.', 'system');
    } else if (data.status === 'error') {
        logToTerminal(`Error de puerto serial: ${data.message}`, 'error');
    }
    updateUIState();
}

// Handle incoming sensor data frame
function handleIncomingData(data) {
    // Round to 1 decimal place
    const temp = parseFloat(data.temp).toFixed(1);
    const hum = parseFloat(data.hum).toFixed(1);
    const ldr = parseFloat(data.ldr).toFixed(1);

    // Update displays
    tempVal.textContent = temp;
    humVal.textContent = hum;
    ldrVal.textContent = ldr;

    // Update trend indicators
    updateTrend('temp', data.temp, tempIndicator);
    updateTrend('hum', data.hum, humIndicator);
    updateTrend('ldr', data.ldr, ldrIndicator);

    // Append to charts
    appendChartData('temp', data.temp);
    appendChartData('hum', data.hum);
    appendChartData('ldr', data.ldr);

    // Draw charts
    drawSVGChart('temp-svg', history.temp, 15, 35); // Temp scale: 15°C to 35°C
    drawSVGChart('hum-svg', history.hum, 0, 100);    // Humidity scale: 0-100%
    drawSVGChart('ldr-svg', history.ldr, 0, 100);    // Light scale: 0-100%
    
    // Log occasionally to prevent spam, or display formatted info
    // (Optional: can print values to terminal)
}

// Update trend text based on previous reading
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

// Add data point to historical array
function appendChartData(key, value) {
    history[key].push(value);
    if (history[key].length > MAX_CHART_POINTS) {
        history[key].shift();
    }
}

// Draw minimalist line chart with gradient shadow under it
function drawSVGChart(svgId, data, minVal, maxVal) {
    const linePath = document.querySelector(`#chart-${svgId} .chart-line`);
    const areaPath = document.querySelector(`#chart-${svgId} .chart-area`);
    
    if (!linePath || !areaPath || data.length < 2) return;
    
    const svgWidth = 300;
    const svgHeight = 80;
    const padding = 6;
    
    const points = data.map((val, index) => {
        // Calculate X: spaced evenly across width
        const x = (index / (data.length - 1)) * svgWidth;
        
        // Calculate Y: map value to height (minVal -> bottom, maxVal -> top)
        let normalized = (val - minVal) / (maxVal - minVal);
        normalized = Math.max(0, Math.min(1, normalized)); // Clamp between 0 and 1
        
        const y = svgHeight - padding - (normalized * (svgHeight - padding * 2));
        return { x, y };
    });
    
    // Generate SVG path commands for line (smooth curves or simple segments)
    // We will use standard lines for simplicity and cleanliness
    let dLine = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
        dLine += ` L ${points[i].x} ${points[i].y}`;
    }
    
    // Set line path
    linePath.setAttribute('d', dLine);
    
    // Generate closed path for area fill (shaded color under the graph)
    const dArea = `${dLine} L ${points[points.length - 1].x} ${svgHeight} L ${points[0].x} ${svgHeight} Z`;
    areaPath.setAttribute('d', dArea);
}

// Fill dropdown list with COM ports, default to COM3 if available
function populatePorts(ports, activePortName) {
    portSelect.innerHTML = '';
    
    if (ports.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Sin puertos';
        portSelect.appendChild(opt);
        return;
    }

    ports.forEach(port => {
        const opt = document.createElement('option');
        opt.value = port;
        opt.textContent = port;
        portSelect.appendChild(opt);
    });

    // Auto-select priority logic:
    // 1. If there's an active port from server, keep it selected.
    // 2. Otherwise, if COM3 is in the list, choose it.
    // 3. Otherwise, choose the first option.
    if (activePortName) {
        portSelect.value = activePortName;
    } else if (ports.includes('COM3')) {
        portSelect.value = 'COM3';
    } else {
        portSelect.value = ports[0];
    }
}

// Update UI elements based on connection states
function updateUIState() {
    if (!isSocketConnected) {
        statusBadge.textContent = 'Servidor Caído';
        statusBadge.className = 'badge badge-disconnected';
        connectBtn.textContent = 'Conectar';
        connectBtn.className = 'btn btn-primary';
        connectBtn.disabled = true;
        scanBtn.disabled = true;
        recordBtn.disabled = true;
        return;
    }

    connectBtn.disabled = false;
    scanBtn.disabled = false;

    if (isSerialConnected) {
        statusBadge.textContent = `Conectado: ${portSelect.value}`;
        statusBadge.className = 'badge badge-connected';
        connectBtn.textContent = 'Desconectar';
        connectBtn.className = 'btn btn-primary connected';
        portSelect.disabled = true;
        recordBtn.disabled = false;
    } else {
        statusBadge.textContent = 'Desconectado';
        statusBadge.className = 'badge badge-disconnected';
        connectBtn.textContent = 'Conectar';
        connectBtn.className = 'btn btn-primary';
        portSelect.disabled = false;
        recordBtn.disabled = true;
    }

    updateRecordingUI();
}

// Update the recording button and flashing badge layout
function updateRecordingUI() {
    if (isRecordingActive && isSerialConnected) {
        recordingBadge.classList.remove('hidden');
        recordBtn.textContent = 'Detener Grabación';
        recordBtn.className = 'btn btn-record recording-active';
    } else {
        recordingBadge.classList.add('hidden');
        recordBtn.textContent = 'Grabar Datos';
        recordBtn.className = 'btn btn-record';
    }
}

// Event Listeners setup
function setupEventListeners() {
    // Port Connection
    connectBtn.addEventListener('click', () => {
        if (!isSocketConnected) return;

        if (isSerialConnected) {
            logToTerminal(`Solicitando desconectar de ${portSelect.value}...`, 'system');
            socket.send(JSON.stringify({ command: 'disconnect' }));
        } else {
            const selectedPort = portSelect.value;
            if (!selectedPort) {
                logToTerminal('Por favor, seleccione un puerto COM válido.', 'error');
                return;
            }
            logToTerminal(`Solicitando conectar a puerto: ${selectedPort}...`, 'system');
            socket.send(JSON.stringify({ command: 'connect', port: selectedPort }));
        }
    });

    // Scan ports
    scanBtn.addEventListener('click', () => {
        if (!isSocketConnected) return;
        logToTerminal('Buscando puertos COM disponibles...', 'system');
        socket.send(JSON.stringify({ command: 'get_ports' }));
    });

    // Recording Toggle
    recordBtn.addEventListener('click', () => {
        if (!isSocketConnected || !isSerialConnected) return;

        if (isRecordingActive) {
            socket.send(JSON.stringify({ command: 'stop_recording' }));
        } else {
            socket.send(JSON.stringify({ command: 'start_recording' }));
        }
    });

    // Clear Terminal logs
    clearLogBtn.addEventListener('click', () => {
        logTerminal.innerHTML = '';
        logToTerminal('Consola limpia.', 'system');
    });
}

// Start client on page load
window.addEventListener('DOMContentLoaded', init);
