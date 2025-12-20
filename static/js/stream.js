// --- SCRAPER STREAM LOGIC ---

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const logsDiv = document.getElementById('logs');
const statusBadge = document.getElementById('statusBadge');
const sitemapInput = document.getElementById('sitemapUrl');
let eventSource = null;

// Add Input Listener for Validation
sitemapInput.addEventListener('input', validateState);

function startScraping() {
    const url = sitemapInput.value.trim();
    let sDate, eDate;

    // Use Calendar State (Global var searchMode)
    if (searchMode === 'today') {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        sDate = `${year}-${month}-${day}`;
        eDate = sDate;
    } else if (searchMode === 'yesterday') {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const year = yesterday.getFullYear();
        const month = String(yesterday.getMonth() + 1).padStart(2, '0');
        const day = String(yesterday.getDate()).padStart(2, '0');
        sDate = `${year}-${month}-${day}`;
        eDate = sDate;
    } else {
        if (!finalStart || !finalEnd) {
            alert("Please pick a date range first.");
            return;
        }
        // Format Custom Dates
        const sYear = finalStart.getFullYear();
        const sMonth = String(finalStart.getMonth() + 1).padStart(2, '0');
        const sDay = String(finalStart.getDate()).padStart(2, '0');
        sDate = `${sYear}-${sMonth}-${sDay}`;

        const eYear = finalEnd.getFullYear();
        const eMonth = String(finalEnd.getMonth() + 1).padStart(2, '0');
        const eDay = String(finalEnd.getDate()).padStart(2, '0');
        eDate = `${eYear}-${eMonth}-${eDay}`;
    }

    if (!url) return;

    // UI Init
    if (eventSource) eventSource.close();
    logsDiv.innerHTML = '';
    startBtn.disabled = true;
    startBtn.classList.add('opacity-50', 'cursor-not-allowed');
    startBtn.innerText = 'Running...';
    stopBtn.disabled = false;
    stopBtn.classList.remove('bg-ios-input', 'text-ios-gray2', 'disabled:opacity-50');
    stopBtn.classList.add('bg-ios-red', 'text-white');
    statusBadge.classList.replace('bg-ios-input', 'bg-ios-green');
    statusBadge.classList.replace('text-ios-subtext', 'text-white');
    statusBadge.innerText = 'Active';

    eventSource = new EventSource(`/stream?sitemap_url=${encodeURIComponent(url)}&start_date=${sDate}&end_date=${eDate}`);

    eventSource.onmessage = (e) => {
        const data = e.data;
        if (data === 'close') { stopScraping(true); return; }
        if (data.startsWith('[DOWNLOAD]')) { openDownloadModal(data.replace('[DOWNLOAD] ', '').trim()); return; }

        let cls = 'text-gray-400';
        let txt = data;
        if (data.includes('[FOUND]')) { cls = 'text-ios-green font-semibold'; txt = "✓ " + data.replace('[FOUND] ', ''); }
        else if (data.includes('[WARN]')) cls = 'text-ios-red';
        else if (data.includes('[INFO]')) cls = 'text-ios-blue';

        const div = document.createElement('div');
        div.className = `mb-1 ${cls}`;
        div.textContent = txt;
        logsDiv.appendChild(div);
        logsDiv.scrollTop = logsDiv.scrollHeight;
    };
    eventSource.onerror = () => stopScraping(false);
}

function manualStop() { stopScraping(false); }

function stopScraping(complete) {
    if (eventSource) { eventSource.close(); eventSource = null; }
    startBtn.disabled = false;
    startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    startBtn.innerText = 'Start';
    stopBtn.disabled = true;
    stopBtn.classList.add('bg-ios-input', 'text-ios-gray2');
    stopBtn.classList.remove('bg-ios-red', 'text-white');
    statusBadge.classList.replace('bg-ios-green', 'bg-ios-input');
    statusBadge.classList.replace('text-white', 'text-ios-subtext');
    statusBadge.innerText = complete ? 'Done' : 'Stopped';
}
