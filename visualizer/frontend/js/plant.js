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

const plantSvg   = document.getElementById('plant-svg');
const stateBadge = document.getElementById('plant-state-badge');
const classText  = document.getElementById('plant-class-text');
const alertMsg   = document.getElementById('plant-alert-msg');
const alertText  = document.getElementById('plant-alert-text');

export function updatePlantState(alert) {
    const key   = String(alert !== undefined && alert !== null ? alert : -1);
    const state = PLANT_STATES[key] ?? PLANT_STATES['-1'];

    plantSvg.setAttribute('class', state.cls);
    stateBadge.className   = `plant-state-badge ${state.badge}`;
    stateBadge.textContent = state.label;
    classText.textContent  = CLASS_LABELS[key] ?? 'Clasificación desconocida';

    if (state.alert) {
        alertMsg.classList.remove('hidden');
        alertText.textContent = state.msg;
    } else {
        alertMsg.classList.add('hidden');
    }
}
