const METRIC_CONFIG = {
    distance_km:              { label: '距离 (km)',              color: '#4e73df', axis: 'y',  type: 'line' },
    avg_pace_s_per_km:        { label: '配速',                   color: '#e74a3b', axis: 'y',  type: 'line', pace: true },
    duration_min:             { label: '时长 (分钟)',            color: '#858796', axis: 'y',  type: 'line' },
    avg_heart_rate:           { label: '平均心率 (bpm)',         color: '#f6c23e', axis: 'y1', type: 'line' },
    max_heart_rate:           { label: '最大心率 (bpm)',         color: '#e74a3b', axis: 'y1', type: 'line' },
    avg_cadence:              { label: '步频 (spm)',             color: '#36b9cc', axis: 'y1', type: 'line' },
    avg_stride_length_cm:     { label: '步幅 (cm)',              color: '#1cc88a', axis: 'y1', type: 'line' },
    elevation_gain_m:         { label: '累计爬升 (m)',           color: '#f6c23e', axis: 'y2', type: 'line' },
    calories:                 { label: '卡路里',                 color: '#858796', axis: 'y2', type: 'line' },
    avg_temperature_c:        { label: '温度 (°C)',              color: '#e74a3b', axis: 'y2', type: 'line' },
    training_effect_aerobic:   { label: '有氧训练效果',           color: '#4e73df', axis: 'y2', type: 'line' },
    training_effect_anaerobic: { label: '无氧训练效果',           color: '#e74a3b', axis: 'y2', type: 'line' },
    vo2max:                    { label: '最大摄氧量',             color: '#1cc88a', axis: 'y2', type: 'line' },
};

function formatPaceSeconds(v) {
    if (!v || v <= 0) return '--';
    const m = Math.floor(v / 60);
    const s = Math.floor(v % 60);
    return m + "'" + String(s).padStart(2, '0') + '"';
}

let _metricsCache = null;

function initDashboardMetricsChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const athleteSel = document.getElementById('metricsAthleteFilter');
    const primarySel = document.getElementById('primaryMetric');
    const secondarySel = document.getElementById('secondaryMetric');
    const daysSel = document.getElementById('metricsDaysFilter');
    let chart = null;

    function fetchData() {
        const params = new URLSearchParams();
        const aid = athleteSel ? athleteSel.value : '';
        if (aid) params.set('athlete_id', aid);
        const days = daysSel ? daysSel.value : '90';
        params.set('days', days);
        const url = canvas.dataset.apiUrl + '?' + params.toString();
        return fetch(url).then(r => r.json()).then(data => {
            _metricsCache = data;
            return data;
        });
    }

    function buildChart(data) {
        if (chart) { chart.destroy(); chart = null; }

        const primaryKey = primarySel ? primarySel.value : 'distance_km';
        const secondaryKey = secondarySel ? secondarySel.value : '';
        const keys = [primaryKey];
        if (secondaryKey) keys.push(secondaryKey);

        const usedAxes = new Set();
        const datasets = keys.map(k => {
            const cfg = METRIC_CONFIG[k];
            usedAxes.add(cfg.axis);
            return {
                label: cfg.label,
                data: data.map(d => d[k]),
                type: cfg.type,
                backgroundColor: cfg.type === 'bar' ? cfg.color : undefined,
                borderColor: cfg.type === 'line' ? cfg.color : undefined,
                fill: cfg.type === 'line' ? false : undefined,
                tension: cfg.type === 'line' ? 0.3 : undefined,
                pointRadius: cfg.type === 'line' ? 3 : undefined,
                yAxisID: cfg.axis,
                order: cfg.type === 'bar' ? 1 : 0,
            };
        });

        const scales = {};
        for (const ax of usedAxes) {
            const cfg = keys.map(k => METRIC_CONFIG[k]).find(c => c.axis === ax);
            const isPace = cfg && cfg.pace;
            scales[ax] = {
                type: 'linear',
                position: ax === 'y' ? 'left' : 'right',
                title: { display: true, text: cfg ? cfg.label : '' },
                grid: { drawOnChartArea: ax === 'y' },
                ticks: isPace ? {
                    callback: function(v) { return formatPaceSeconds(v); }
                } : undefined,
            };
        }

        chart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.map(d => d.date),
                datasets: datasets,
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const key = keys[ctx.datasetIndex];
                                const cfg = METRIC_CONFIG[key];
                                const v = ctx.raw;
                                if (v == null) return '--';
                                if (cfg.pace) return cfg.label + ': ' + formatPaceSeconds(v);
                                return cfg.label + ': ' + (typeof v === 'number' ? v.toFixed(1) : v);
                            }
                        }
                    }
                },
                scales: scales,
            },
        });
    }

    function refresh() {
        if (_metricsCache) {
            buildChart(_metricsCache);
        } else {
            fetchData().then(buildChart);
        }
    }

    function refreshData() {
        _metricsCache = null;
        fetchData().then(buildChart);
    }

    // Wire up controls
    if (athleteSel) athleteSel.addEventListener('change', refreshData);
    if (daysSel) daysSel.addEventListener('change', refreshData);
    if (primarySel) primarySel.addEventListener('change', refresh);
    if (secondarySel) secondarySel.addEventListener('change', refresh);

    // Initial load
    fetchData().then(buildChart);
}

function initAthleteCharts(athleteId) {
    const daysSel = document.getElementById('athleteDaysFilter');

    const chartDefs = [
        { id: 'athleteChartDistance',   keys: ['distance_km'],              title: '距离 (km)' },
        { id: 'athleteChartDuration',   keys: ['duration_min'],             title: '时长 (分钟)' },
        { id: 'athleteChartPace',       keys: ['avg_pace_s_per_km'],        title: '配速',           pace: true },
        { id: 'athleteChartHr',         keys: ['avg_heart_rate', 'max_heart_rate'], title: '心率 (bpm)' },
        { id: 'athleteChartCadence',    keys: ['avg_cadence'],              title: '步频 (spm)' },
        { id: 'athleteChartStride',     keys: ['avg_stride_length_cm'],     title: '步幅 (cm)' },
        { id: 'athleteChartElevation',  keys: ['elevation_gain_m'],         title: '累计爬升 (m)' },
        { id: 'athleteChartTraining',   keys: ['training_effect_aerobic', 'training_effect_anaerobic'], title: '训练效果' },
    ];

    const charts = {};

    function destroyAll() {
        for (const k in charts) {
            if (charts[k]) { charts[k].destroy(); charts[k] = null; }
        }
    }

    function buildAll(data) {
        destroyAll();
        const labels = data.map(function(d) { return d.date; });

        chartDefs.forEach(function(def) {
            const canvas = document.getElementById(def.id);
            if (!canvas) return;

            const datasets = def.keys.map(function(k) {
                const cfg = METRIC_CONFIG[k];
                return {
                    label: cfg.label,
                    data: data.map(function(d) { return d[k]; }),
                    borderColor: cfg.color,
                    backgroundColor: cfg.color + '22',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                };
            });

            const isPace = def.pace;
            charts[def.id] = new Chart(canvas, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: def.keys.length > 1, position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: function(ctx) {
                                    const key = def.keys[ctx.datasetIndex];
                                    const cfg = METRIC_CONFIG[key];
                                    const v = ctx.raw;
                                    if (v == null) return '--';
                                    if (cfg.pace) return cfg.label + ': ' + formatPaceSeconds(v);
                                    return cfg.label + ': ' + (typeof v === 'number' ? v.toFixed(1) : v);
                                }
                            }
                        }
                    },
                    scales: {
                        x: { ticks: { font: { size: 9 }, maxTicksLimit: 8 } },
                        y: {
                            title: { display: true, text: def.title, font: { size: 10 } },
                            ticks: isPace ? { font: { size: 9 }, callback: function(v) { return formatPaceSeconds(v); } } : { font: { size: 9 } },
                        }
                    }
                }
            });
        });
    }

    function fetchAndBuild() {
        const days = daysSel ? daysSel.value : '90';
        const params = new URLSearchParams();
        params.set('athlete_id', athleteId);
        params.set('days', days);
        return fetch('/api/activities/metrics?' + params.toString())
            .then(function(r) { return r.json(); })
            .then(buildAll);
    }

    if (daysSel) daysSel.addEventListener('change', fetchAndBuild);
    fetchAndBuild();
}

function initWeeklyDistanceChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    fetch(canvas.dataset.url)
        .then(r => r.json())
        .then(data => {
            new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.week),
                    datasets: [{
                        label: '距离 (km)',
                        data: data.map(d => d.distance_km),
                        backgroundColor: '#4e73df',
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { title: { display: true, text: '距离 (公里)' } }
                    }
                }
            });
        });
}

function initPaceTrendChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    fetch(canvas.dataset.url)
        .then(r => r.json())
        .then(data => {
            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: data.map(d => d.date),
                    datasets: [{
                        label: '配速 (秒/公里)',
                        data: data.map(d => d.pace),
                        borderColor: '#e74a3b',
                        backgroundColor: 'rgba(231,74,59,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: {
                            title: { display: true, text: '配速 (秒/公里)' },
                            ticks: {
                                callback: function(v) {
                                    const m = Math.floor(v / 60);
                                    const s = Math.floor(v % 60);
                                    return m + "'" + String(s).padStart(2, '0') + '"';
                                }
                            }
                        },
                        x: { title: { display: true, text: '日期' } }
                    }
                }
            });
        });
}

function initDashboardWeeklyChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    fetch(canvas.dataset.url)
        .then(r => r.json())
        .then(data => {
            new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.week),
                    datasets: [{
                        label: '总距离 (km)',
                        data: data.map(d => d.distance_km),
                        backgroundColor: '#1cc88a',
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { title: { display: true, text: '总距离 (公里)' } }
                    }
                }
            });
        });
}

function formatDurationSeconds(totalSec) {
    if (!totalSec && totalSec !== 0) return '--';
    var h = Math.floor(totalSec / 3600);
    var m = Math.floor((totalSec % 3600) / 60);
    var s = Math.floor(totalSec % 60);
    if (h > 0) return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    return m + ':' + String(s).padStart(2, '0');
}

function initActivityTimeSeries(activityId) {
    var hrCanvas = document.getElementById('tsChartHr');
    var paceCanvas = document.getElementById('tsChartPace');
    var cadenceCanvas = document.getElementById('tsChartCadence');
    var strideCanvas = document.getElementById('tsChartStride');
    if (!hrCanvas && !paceCanvas && !cadenceCanvas && !strideCanvas) return;

    fetch('/api/activities/' + activityId + '/time-series')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!Array.isArray(data) || data.length === 0) return;

            var labels = data.map(function(d) { return formatDurationSeconds(d.time); });
            var hrData = data.map(function(d) { return d.heart_rate; });
            var paceData = data.map(function(d) { return d.pace; });
            var cadenceData = data.map(function(d) { return d.cadence; });
            var strideData = data.map(function(d) { return d.stride; });

            var commonOpts = function(title, color) {
                return {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: function(ctx) {
                            var v = ctx.raw;
                            if (v == null) return '--';
                            return title + ': ' + v.toFixed(1);
                        }}}
                    },
                    scales: {
                        x: { title: { display: true, text: '时间', font: { size: 10 } }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
                        y: { title: { display: true, text: title, font: { size: 10 } }, ticks: { font: { size: 9 } } }
                    }
                };
            };

            if (hrCanvas) {
                new Chart(hrCanvas, {
                    type: 'line',
                    data: { labels: labels, datasets: [{
                        label: '心率', data: hrData, borderColor: '#e74a3b',
                        backgroundColor: '#e74a3b', showLine: false, pointRadius: 2, pointStyle: 'circle',
                    }]},
                    options: commonOpts('心率 (bpm)')
                });
            }

            if (paceCanvas) {
                new Chart(paceCanvas, {
                    type: 'line',
                    data: { labels: labels, datasets: [{
                        label: '配速', data: paceData, borderColor: '#4e73df',
                        backgroundColor: '#4e73df', showLine: false, pointRadius: 2, pointStyle: 'circle',
                    }]},
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: { label: function(ctx) {
                                var v = ctx.raw;
                                if (v == null) return '--';
                                return '配速: ' + formatPaceSeconds(v);
                            }}}
                        },
                        scales: {
                            x: { title: { display: true, text: '时间', font: { size: 10 } }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
                            y: { title: { display: true, text: '配速', font: { size: 10 } },
                                ticks: { font: { size: 9 }, callback: function(v) { return formatPaceSeconds(v); } },
                                reverse: true,
                            }
                        }
                    }
                });
            }

            if (cadenceCanvas) {
                new Chart(cadenceCanvas, {
                    type: 'line',
                    data: { labels: labels, datasets: [{
                        label: '步频', data: cadenceData, borderColor: '#36b9cc',
                        backgroundColor: '#36b9cc', showLine: false, pointRadius: 2, pointStyle: 'circle',
                    }]},
                    options: commonOpts('步频 (spm)')
                });
            }

            if (strideCanvas) {
                new Chart(strideCanvas, {
                    type: 'line',
                    data: { labels: labels, datasets: [{
                        label: '步幅', data: strideData, borderColor: '#1cc88a',
                        backgroundColor: '#1cc88a', showLine: false, pointRadius: 2, pointStyle: 'circle',
                    }]},
                    options: commonOpts('步幅 (cm)')
                });
            }
        });
}

function initLapDetailCharts(laps) {
    const labels = laps.map(function(l) { return '圈' + l.lap_number; });

    function val(d, k) {
        var v = d[k];
        if (v == null || v === 0) return null;
        if (k === 'distance_m') return parseFloat((v / 1000).toFixed(2));
        if (k === 'duration_s') return parseFloat((v / 60).toFixed(1));
        return v;
    }

    var chartDefs = [
        { id: 'lapChartDistance',  key: 'distance_m',          label: '距离 (km)',     color: '#4e73df' },
        { id: 'lapChartDuration',  key: 'duration_s',          label: '时长 (分钟)',   color: '#858796' },
        { id: 'lapChartPace',      key: 'avg_pace_s_per_km',   label: '配速',          color: '#e74a3b', pace: true },
        { id: 'lapChartHr',        keys: ['avg_heart_rate', 'max_heart_rate'], labels: ['平均心率', '最大心率'], colors: ['#f6c23e', '#e74a3b'] },
        { id: 'lapChartCadence',   key: 'avg_cadence',         label: '步频 (spm)',    color: '#36b9cc' },
        { id: 'lapChartElevation', key: 'elevation_gain_m',    label: '累计爬升 (m)',  color: '#f6c23e' },
    ];

    chartDefs.forEach(function(def) {
        var canvas = document.getElementById(def.id);
        if (!canvas) return;

        var datasets;
        if (def.keys) {
            datasets = def.keys.map(function(k, i) {
                return {
                    label: def.labels[i],
                    data: laps.map(function(l) { return l[k]; }),
                    borderColor: def.colors[i],
                    backgroundColor: def.colors[i] + '22',
                    fill: false, tension: 0.3, pointRadius: 3,
                };
            });
        } else {
            datasets = [{
                label: def.label,
                data: laps.map(function(l) { return val(l, def.key); }),
                borderColor: def.color,
                backgroundColor: def.color + '22',
                fill: false, tension: 0.3, pointRadius: 3,
            }];
        }

        var isPace = def.pace;
        new Chart(canvas, {
            type: def.keys ? 'line' : 'bar',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: !!(def.keys), position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
                },
                scales: {
                    x: { ticks: { font: { size: 9 } } },
                    y: {
                        title: { display: true, text: def.label || '心率 (bpm)', font: { size: 10 } },
                        ticks: isPace ? { font: { size: 9 }, callback: function(v) { return formatPaceSeconds(v); } } : { font: { size: 9 } },
                    }
                }
            }
        });
    });
}

function initLapCharts(laps) {
    const paceCanvas = document.getElementById('lapPaceChart');
    const hrCanvas = document.getElementById('lapHrChart');

    if (paceCanvas) {
        new Chart(paceCanvas, {
            type: 'bar',
            data: {
                labels: laps.map(l => '圈' + l.lap_number),
                datasets: [{
                    label: '配速 (秒/公里)',
                    data: laps.map(l => l.avg_pace_s_per_km),
                    backgroundColor: '#4e73df',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const v = ctx.raw;
                                if (!v) return '--';
                                const m = Math.floor(v / 60);
                                const s = Math.floor(v % 60);
                                return m + "'" + String(s).padStart(2, '0') + '"';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: { display: true, text: '配速 (秒/公里)' },
                        ticks: {
                            callback: function(v) {
                                const m = Math.floor(v / 60);
                                const s = Math.floor(v % 60);
                                return m + "'" + String(s).padStart(2, '0') + '"';
                            }
                        }
                    }
                }
            }
        });
    }

    if (hrCanvas) {
        new Chart(hrCanvas, {
            type: 'bar',
            data: {
                labels: laps.map(l => '圈' + l.lap_number),
                datasets: [{
                    label: '心率 (bpm)',
                    data: laps.map(l => l.avg_heart_rate),
                    backgroundColor: '#e74a3b',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { title: { display: true, text: '心率 (bpm)' } }
                }
            }
        });
    }
}
