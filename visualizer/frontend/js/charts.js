/* global echarts */

const MAX_POINTS = 40;
const history    = { temp: [], hum: [], ldr: [] };

let chartTemp = null;
let chartHum  = null;
let chartLdr  = null;

export function initCharts() {
    chartTemp = echarts.init(document.getElementById('chart-temp'), null, { renderer: 'canvas' });
    chartHum  = echarts.init(document.getElementById('chart-hum'),  null, { renderer: 'canvas' });
    chartLdr  = echarts.init(document.getElementById('chart-ldr'),  null, { renderer: 'canvas' });

    chartTemp.setOption(_makeOption('#d9383a', 15, 35));
    chartHum.setOption(_makeOption('#107c41',   0, 100));
    chartLdr.setOption(_makeOption('#b7791f',   0, 100));

    window.addEventListener('resize', () => {
        chartTemp.resize();
        chartHum.resize();
        chartLdr.resize();
    });
}

export function pushData(key, value) {
    history[key].push(value);
    if (history[key].length > MAX_POINTS) history[key].shift();
    _update(key);
}

function _update(key) {
    const chart = { temp: chartTemp, hum: chartHum, ldr: chartLdr }[key];
    const data  = history[key];
    if (!chart || data.length < 2) return;
    chart.setOption({
        xAxis:  { data: data.map((_, i) => i) },
        series: [{ data }],
    });
}

function _makeOption(hexColor, minVal, maxVal) {
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    return {
        animation: false,
        grid:   { top: 3, bottom: 3, left: 0, right: 0 },
        xAxis:  { type: 'category', show: false, boundaryGap: false, data: [] },
        yAxis:  { type: 'value',    show: false, min: minVal, max: maxVal },
        tooltip: {
            trigger: 'axis',
            formatter: params => params[0].value.toFixed(1),
            backgroundColor: 'rgba(17,17,17,0.82)',
            borderColor: 'transparent',
            padding: [4, 8],
            textStyle: { color: '#fff', fontSize: 11, fontFamily: 'monospace' },
        },
        series: [{
            type:        'line',
            smooth:      true,
            symbol:      'none',
            data:        [],
            lineStyle:   { width: 2.2, color: hexColor },
            areaStyle:   {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${r},${g},${b},0.14)` },
                    { offset: 1, color: `rgba(${r},${g},${b},0.01)` },
                ]),
            },
        }],
    };
}
