const btnAutoStart = document.getElementById('btnAutoStart');
const autoUrlInput = document.getElementById('autoUrl');
const autoLogsDiv = document.getElementById('autoLogs');
let autoEventSource = null;

function startAutoDiscovery() {
    const url = autoUrlInput.value.trim();
    if (!url) {
        alert("Please enter a website URL.");
        return;
    }

    // --- DATE LOGIC (Reused from stream.js concept) ---
    // Accessing globals from calendar.js
    let sDate, eDate;
    if (typeof searchMode !== 'undefined' && searchMode === 'today') {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        sDate = `${year}-${month}-${day}`;
        eDate = sDate;
    } else if (typeof searchMode !== 'undefined' && searchMode === 'yesterday') {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const year = yesterday.getFullYear();
        const month = String(yesterday.getMonth() + 1).padStart(2, '0');
        const day = String(yesterday.getDate()).padStart(2, '0');
        sDate = `${year}-${month}-${day}`;
        eDate = sDate;
    } else {
        if (!finalStart || !finalEnd) {
            alert("Please pick a date range first (in the top section).");
            return;
        }
        const sYear = finalStart.getFullYear();
        const sMonth = String(finalStart.getMonth() + 1).padStart(2, '0');
        const sDay = String(finalStart.getDate()).padStart(2, '0');
        sDate = `${sYear}-${sMonth}-${sDay}`;

        const eYear = finalEnd.getFullYear();
        const eMonth = String(finalEnd.getMonth() + 1).padStart(2, '0');
        const eDay = String(finalEnd.getDate()).padStart(2, '0');
        eDate = `${eYear}-${eMonth}-${eDay}`;
    }

    // UI State
    if (autoEventSource) autoEventSource.close();
    autoLogsDiv.innerHTML = '';
    btnAutoStart.disabled = true;
    btnAutoStart.classList.add('opacity-50', 'cursor-not-allowed');
    btnAutoStart.innerText = 'Scanning...';

    // Connect
    const finalUrl = `/stream_auto?homepage_url=${encodeURIComponent(url)}&start_date=${sDate}&end_date=${eDate}`;
    autoEventSource = new EventSource(finalUrl);

    autoEventSource.onmessage = (e) => {
        const data = e.data;
        if (data === 'close') { stopAutoDiscovery(true); return; }
        if (data.startsWith('[DOWNLOAD]')) {
            // Use global modal from ui.js
            if (typeof openDownloadModal === 'function') openDownloadModal(data.replace('[DOWNLOAD] ', '').trim());
            return;
        }

        let cls = 'text-gray-400';
        let txt = data;

        if (data.includes('[SUCCESS]') || data.includes('[FOUND]')) { cls = 'text-ios-green font-semibold'; }
        else if (data.includes('[ERROR]') || data.includes('[FAILURE]')) { cls = 'text-ios-red font-bold'; }
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
    btnAutoStart.disabled = false;
    btnAutoStart.classList.remove('opacity-50', 'cursor-not-allowed');
    btnAutoStart.innerText = complete ? 'Done within Range' : 'Retry';
}
