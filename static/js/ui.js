// --- UI & THEME LOGIC ---

// Theme Toggle
function toggleTheme() {
    const body = document.body;
    if (body.classList.contains('dark')) {
        body.classList.remove('dark');
        localStorage.setItem('theme', 'light');
    } else {
        body.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }
}
// Init Theme
if (localStorage.getItem('theme') === 'light') document.body.classList.remove('dark');
else document.body.classList.add('dark');


// --- UI STATE VALIDATION ---
function setActiveBtn(activeId, otherIds) {
    document.getElementById(activeId).className = "flex-1 py-2 text-xs font-semibold rounded-lg bg-ios-card text-ios-text shadow-sm transition-all border border-ios-border";
    otherIds.forEach(id => {
        document.getElementById(id).className = "flex-1 py-2 text-xs font-semibold rounded-lg text-ios-subtext hover:text-ios-text transition-all border border-transparent";
    });
}

function setMode(mode) {
    searchMode = mode; // Global logic

    if (mode === 'today') {
        setActiveBtn('btnToday', ['btnYesterday', 'btnCustom']);
        updateDisplayRange();
    } else if (mode === 'yesterday') {
        setActiveBtn('btnYesterday', ['btnToday', 'btnCustom']);
        updateDisplayRange();
    } else {
        setActiveBtn('btnCustom', ['btnToday', 'btnYesterday']);
        openCalendar();
    }
    validateState();
}

function validateState() {
    const url = document.getElementById('sitemapUrl').value.trim();
    const startBtn = document.getElementById('startBtn');
    const hasUrl = url.length > 0;

    let hasDates = false;
    if (typeof searchMode !== 'undefined' && (searchMode === 'today' || searchMode === 'yesterday')) {
        hasDates = true;
    } else {
        // In custom mode, user must have picked dates
        hasDates = (typeof finalStart !== 'undefined' && finalStart !== null && finalEnd !== null);
    }

    if (hasUrl && hasDates) {
        startBtn.disabled = false;
        startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
        startBtn.disabled = true;
        startBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
}

// --- MODALS (Instructions & Download) ---

// Unified Helper
function showModal(cardId) {
    const overlay = document.getElementById('modalOverlay');
    const card = document.getElementById(cardId);

    // Hide all other cards first
    ['instCard', 'calendarCard', 'dlCard'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
        document.getElementById(id).classList.remove('scale-100');
        document.getElementById(id).classList.add('scale-95');
    });

    // Show Overlay
    overlay.classList.remove('hidden');
    // Show specific card
    card.classList.remove('hidden');

    // Animate in
    setTimeout(() => {
        overlay.classList.remove('opacity-0');
        card.classList.remove('scale-95');
        card.classList.add('scale-100');
    }, 10);
}

function closeModal() {
    const overlay = document.getElementById('modalOverlay');
    // Find visible card
    const visibleCard = ['instCard', 'calendarCard', 'dlCard'].map(id => document.getElementById(id)).find(el => !el.classList.contains('hidden'));

    if (visibleCard) {
        visibleCard.classList.remove('scale-100');
        visibleCard.classList.add('scale-95');
    }
    overlay.classList.add('opacity-0');

    setTimeout(() => {
        overlay.classList.add('hidden');
        if (visibleCard) visibleCard.classList.add('hidden');

        // If closing Calendar without selection, revert
        if (typeof searchMode !== 'undefined' && searchMode === 'custom' && !finalStart) {
            setMode('today');
        }
    }, 200);
}

// Specific Openers
function openInstructions() { showModal('instCard'); }
function closeInstructions() { closeModal(); } // Legacy alias

function downloadFile(f) { window.location.href = `/download/${f}`; closeModal(); }

function openDownloadModal(filename) {
    const btn = document.getElementById('dlConfirmBtn');
    btn.onclick = () => downloadFile(filename);
    showModal('dlCard');
}
function closeDownloadModal() { closeModal(); } // Legacy alias

// Initial Validation
document.addEventListener('DOMContentLoaded', () => {
    updateDisplayRange();
    validateState();
});
