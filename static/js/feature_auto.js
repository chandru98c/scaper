const btnAutoStart = document.getElementById('btnAutoStart');
const btnAutoStop = document.getElementById('btnAutoStop');
const autoUrlInput = document.getElementById('autoUrl');
const autoLogsDiv = document.getElementById('autoLogs');
const rangeDisplay = document.getElementById('rangeDisplay');
let autoEventSource = null;

// State
let currentAutoMode = 'today'; // today, yesterday, both, range
let currentRangeVal = 0;

// Helper to calculate Date String (YYYY-MM-DD)
function getDateStr(daysBack = 0) {
    const d = new Date();
    d.setDate(d.getDate() - daysBack);
    return {
        str: d.toISOString().split('T')[0],
        obj: d
    };
}

// Helper: Format Date for Display (Dec 20)
function formatDate(dObj) {
    return dObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Mode Selector
function setAutoMode(mode, val = 0) {
    currentAutoMode = mode;
    currentRangeVal = val;

    // UI Reset
    const standardIds = ['btnAutoToday', 'btnAutoYesterday', 'btnAutoBoth'];
    const rangeIds = [2, 3, 4, 5, 6].map(n => `btnRange${n}`);
    const allIds = [...standardIds, ...rangeIds];

    allIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('bg-ios-card', 'shadow-sm', 'text-ios-text');
            el.classList.add('text-ios-subtext');
        }
    });

    // Activate Specific Button
    let activeId = '';
    if (mode === 'today') activeId = 'btnAutoToday';
    else if (mode === 'yesterday') activeId = 'btnAutoYesterday';
    else if (mode === 'both') activeId = 'btnAutoBoth';
    else if (mode === 'range') activeId = `btnRange${val}`;

    const activeEl = document.getElementById(activeId);
    if (activeEl) {
        activeEl.classList.remove('text-ios-subtext');
        activeEl.classList.add('bg-ios-card', 'shadow-sm', 'text-ios-text');
    }

    // Update Display Text
    updateRangeDisplay();
}

function updateRangeDisplay() {
    let sStr, eStr, sObj, eObj;

    if (currentAutoMode === 'today') {
        const d = getDateStr(0); sStr = d.str; eStr = d.str; sObj = d.obj; eObj = d.obj;
    } else if (currentAutoMode === 'yesterday') {
        const d = getDateStr(1); sStr = d.str; eStr = d.str; sObj = d.obj; eObj = d.obj;
    } else if (currentAutoMode === 'both') {
        const s = getDateStr(1); const e = getDateStr(0);
        sStr = s.str; eStr = e.str; sObj = s.obj; eObj = e.obj;
    } else if (currentAutoMode === 'range') {
        const s = getDateStr(currentRangeVal); const e = getDateStr(0);
        sStr = s.str; eStr = e.str; sObj = s.obj; eObj = e.obj;
    }

    // Show text if Range mode, else hide or show standard? Use requested "show range date next to range title" logic.
    // Actually user said "when selected show the range date next ro range title".
    // I will show it for ALL modes for clarity, or just range.
    // But since the Element is next to "Days Back" title, it makes sense only for Range mode.

    if (currentAutoMode === 'range') {
        rangeDisplay.textContent = `(${formatDate(sObj)} - ${formatDate(eObj)})`;
        rangeDisplay.classList.remove('opacity-0');
    } else {
        rangeDisplay.classList.add('opacity-0');
    }
}

// Validation
function validateAutoState() {
    const url = autoUrlInput.value.trim();
    if (url) {
        btnAutoStart.disabled = false;
        btnAutoStart.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
        btnAutoStart.disabled = true;
        btnAutoStart.classList.add('opacity-50', 'cursor-not-allowed');
    }
}

autoUrlInput.addEventListener('input', validateAutoState);

// Start
function startAutoDiscovery() {
    const url = autoUrlInput.value.trim();
    if (!url) return;

    // Calc Dates
    let sDate, eDate;
    if (currentAutoMode === 'today') {
        sDate = getDateStr(0).str; eDate = sDate;
    } else if (currentAutoMode === 'yesterday') {
        sDate = getDateStr(1).str; eDate = sDate;
    } else if (currentAutoMode === 'both') {
        sDate = getDateStr(1).str; eDate = getDateStr(0).str;
    } else if (currentAutoMode === 'range') {
        sDate = getDateStr(currentRangeVal).str;
        eDate = getDateStr(0).str;
    }

    // Lock UI
    if (autoEventSource) autoEventSource.close();
    autoLogsDiv.innerHTML = '';

    // Disable Controls
    autoUrlInput.disabled = true;
    const allBtns = ['btnAutoToday', 'btnAutoYesterday', 'btnAutoBoth',
        'btnRange2', 'btnRange3', 'btnRange4', 'btnRange5', 'btnRange6'];
    allBtns.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = true;
    });

    btnAutoStart.disabled = true;
    btnAutoStart.classList.add('opacity-50', 'cursor-not-allowed');
    btnAutoStart.innerText = 'Scanning...';

    btnAutoStop.disabled = false;
    btnAutoStop.classList.remove('bg-ios-input', 'text-ios-gray2', 'disabled:opacity-50');
    btnAutoStop.classList.add('bg-ios-red', 'text-white');

    // Connect
    const finalUrl = `/stream_auto?homepage_url=${encodeURIComponent(url)}&start_date=${sDate}&end_date=${eDate}`;
    autoEventSource = new EventSource(finalUrl);

    autoEventSource.onmessage = (e) => {
        const data = e.data;
        if (data === 'close') { stopAutoDiscovery(true); return; }
        if (data.startsWith('[DOWNLOAD]')) {
            if (typeof openDownloadModal === 'function') openDownloadModal(data.replace('[DOWNLOAD] ', '').trim());
            return;
        }

        let cls = 'text-gray-400';
        let txt = data;

        if (data.includes('[SUCCESS]') || data.includes('[FOUND]')) cls = 'text-ios-green font-semibold';
        else if (data.includes('[ERROR]') || data.includes('[FAILURE]')) cls = 'text-ios-red font-bold';
        else if (data.includes('[WARN]')) cls = 'text-yellow-500';
        else if (data.includes('[INFO]')) cls = 'text-ios-blue';

        const div = document.createElement('div');
        div.className = `mb-1 ${cls}`;
        div.textContent = txt;
        autoLogsDiv.appendChild(div);
        autoLogsDiv.scrollTop = autoLogsDiv.scrollHeight;
    };

    autoEventSource.onerror = () => stopAutoDiscovery(false);
}

function stopAutoDiscovery(complete) {
    if (autoEventSource) { autoEventSource.close(); autoEventSource = null; }

    autoUrlInput.disabled = false;
    const allBtns = ['btnAutoToday', 'btnAutoYesterday', 'btnAutoBoth',
        'btnRange2', 'btnRange3', 'btnRange4', 'btnRange5', 'btnRange6'];
    allBtns.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = false;
    });

    btnAutoStart.disabled = false;
    btnAutoStart.classList.remove('opacity-50', 'cursor-not-allowed');
    btnAutoStart.innerText = complete ? 'Done' : 'Retry';

    btnAutoStop.disabled = true;
    btnAutoStop.classList.add('bg-ios-input', 'text-ios-gray2');
    btnAutoStop.classList.remove('bg-ios-red', 'text-white');
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    setAutoMode('today');
    validateAutoState();
});
