// --- CALENDAR LOGIC ---

// State
let searchMode = 'today';
let currentDate = new Date();
// Committed selection (User must confirm modal to update these)
let finalStart = null;
let finalEnd = null;
// Draft selection (Inside modal)
let draftStart = new Date();
let draftEnd = new Date();

const MAX_DAYS = 9;

// Strip time util
function strip(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

// Init drafts to today
draftStart = strip(new Date());
draftEnd = strip(new Date());

// Helper for new start logic
function setNewStart(date, today) {
    draftStart = date;
    // Attempt to range to Today
    if (date.getTime() <= today.getTime()) {
        const diff = (today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24);
        if (diff <= MAX_DAYS) draftEnd = today;
        else draftEnd = date;
    } else {
        draftEnd = date;
    }
}

function updateDisplayRange() {
    const btn = document.getElementById('btnCustom');

    if (searchMode === 'today' || searchMode === 'yesterday' || !finalStart) {
        btn.innerText = "Custom";
        return;
    }

    const options = { month: 'short', day: 'numeric' };
    const sStr = finalStart.toLocaleDateString('en-US', options);
    const eStr = finalEnd.toLocaleDateString('en-US', options);

    if (finalStart.getTime() === finalEnd.getTime()) btn.innerText = sStr;
    else btn.innerText = `${sStr} - ${eStr}`;
}

// --- MODAL & RENDERING ---
function openCalendar() {
    if (finalStart) {
        draftStart = new Date(finalStart);
        draftEnd = new Date(finalEnd);
    } else {
        draftStart = strip(new Date());
        draftEnd = strip(new Date());
    }
    currentDate = new Date(draftStart);
    renderCalendar();

    // Use Unified Modal
    showModal('calendarCard');
}

function closeCalendar() {
    closeModal();
}

function confirmDateSelection() {
    finalStart = new Date(draftStart);
    finalEnd = new Date(draftEnd);
    updateDisplayRange();
    closeCalendar();
    validateState();
}

function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    document.getElementById('currentMonthYear').textContent = new Date(year, month).toLocaleString('default', { month: 'long', year: 'numeric' });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '';

    for (let i = 0; i < firstDay; i++) grid.appendChild(document.createElement('div'));

    const today = strip(new Date());

    for (let d = 1; d <= daysInMonth; d++) {
        const date = new Date(year, month, d);
        const time = date.getTime();
        const el = document.createElement('div');
        el.className = 'day-cell';
        el.textContent = d;

        const sTime = draftStart.getTime();
        const eTime = draftEnd.getTime();

        if (time === sTime) {
            el.classList.add('selected');
            if (eTime > sTime) el.classList.add('range-start');
        }
        if (time === eTime) {
            el.classList.add('selected');
            if (eTime > sTime) el.classList.add('range-end');
        }
        if (time > sTime && time < eTime) el.classList.add('range-bg');
        if (time === today.getTime()) el.classList.add('today');

        el.onclick = () => selectDate(date);
        grid.appendChild(el);
    }
}

function selectDate(date) {
    const time = date.getTime();
    const sTime = draftStart.getTime();
    const today = strip(new Date());

    if (time < sTime) {
        setNewStart(date, today);
    } else if (time > sTime) {
        const diffDays = Math.round((time - sTime) / (1000 * 60 * 60 * 24));
        if (diffDays <= MAX_DAYS) draftEnd = date;
        else setNewStart(date, today);
    } else {
        setNewStart(date, today);
    }
    renderCalendar();
}

function changeMonth(delta) {
    currentDate.setMonth(currentDate.getMonth() + delta);
    renderCalendar();
}
